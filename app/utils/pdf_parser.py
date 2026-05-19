"""PDF 解析模块 - 支持 PyMuPDF4LLM 和 MinerU 两种引擎"""
import logging
import pandas as pd

logger = logging.getLogger("data_analyzer.pdf_parser")


def read_pdf(path, engine="auto", password=""):
    """
    读取 PDF 文件

    Args:
        path: PDF 文件路径
        engine: "auto"(PyMuPDF4LLM优先), "pymupdf4llm", "mineru"
        password: PDF 密码

    Returns:
        pandas DataFrame
    """
    import pymupdf

    # 检测加密
    doc = pymupdf.open(path)
    if doc.is_encrypted:
        if password:
            if not doc.authenticate(password):
                doc.close()
                raise ValueError("PDF 密码错误")
        else:
            doc.close()
            raise ValueError("PDF 文件需要密码")
    doc.close()

    if engine == "mineru":
        return _read_pdf_mineru(path, password)
    elif engine == "pymupdf4llm":
        return _read_pdf_pymupdf4llm(path, password)
    else:
        # 自动：PyMuPDF4LLM 优先
        try:
            return _read_pdf_pymupdf4llm(path, password)
        except Exception as e:
            logger.warning(f"PyMuPDF4LLM 失败，尝试 MinerU: {e}")

        try:
            return _read_pdf_mineru(path, password)
        except Exception as e:
            if "No module named" in str(e):
                logger.info(f"MinerU 不可用: {e}")
            else:
                logger.warning(f"MinerU 也失败: {e}")

        raise ValueError("PDF 解析失败，两种引擎均无法处理")


def _read_pdf_pymupdf4llm(path, password=""):
    """PyMuPDF4LLM 快速模式"""
    import pymupdf4llm
    import pymupdf

    logger.info("使用 PyMuPDF4LLM 快速模式解析 PDF...")

    if password:
        doc = pymupdf.open(path)
        doc.authenticate(password)
        md_text = pymupdf4llm.to_markdown(doc)
        doc.close()
    else:
        md_text = pymupdf4llm.to_markdown(path)

    # 从 Markdown 提取表格
    tables = _extract_tables_from_markdown(md_text)
    if tables:
        all_dfs = []
        for table_lines in tables:
            df = _parse_markdown_table_lines(table_lines)
            if df is not None and not df.empty:
                all_dfs.append(df)

        if all_dfs:
            if len(all_dfs) == 1:
                return all_dfs[0]
            main_cols = max(all_dfs, key=len).shape[1]
            same_structure = [df for df in all_dfs if df.shape[1] == main_cols]
            if same_structure:
                return pd.concat(same_structure, ignore_index=True)
            return max(all_dfs, key=len)

    # 没有表格，返回文本
    lines = [l.strip() for l in md_text.splitlines() if l.strip() and not l.startswith("#")]
    if lines:
        return pd.DataFrame({"内容": lines})

    raise ValueError("PDF 中未找到表格或文本内容")


def _read_pdf_mineru(path, password=""):
    """MinerU AI 高精度模式"""
    import tempfile
    import os
    import pymupdf

    try:
        import transformers  # noqa: F401
        from mineru.cli.common import do_parse
    except Exception as e:
        raise ImportError(f"MinerU 不可用: {e}")

    logger.info("使用 MinerU AI 模式解析 PDF...")

    # 解密 PDF
    doc = pymupdf.open(path)
    if doc.is_encrypted:
        doc.authenticate(password or "")
    pdf_bytes = doc.tobytes(deflate=True)
    doc.close()

    # 调用 MinerU
    temp_dir = tempfile.mkdtemp()
    file_name = os.path.splitext(os.path.basename(path))[0]

    do_parse(
        output_dir=temp_dir,
        pdf_file_names=[file_name],
        pdf_bytes_list=[pdf_bytes],
        p_lang_list=["ch"],
        backend="pipeline",
        parse_method="auto",
        table_enable=True,
        f_dump_md=True,
        f_dump_middle_json=False,
        f_dump_model_output=False,
        f_dump_orig_pdf=False,
        f_dump_content_list=False,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
    )

    # 读取 Markdown 输出
    md_file = os.path.join(temp_dir, file_name, f"{file_name}.md")
    if not os.path.exists(md_file):
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                if f.endswith(".md"):
                    md_file = os.path.join(root, f)
                    break

    if not os.path.exists(md_file):
        raise ValueError("MinerU 未生成 Markdown 输出")

    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()

    logger.info(f"MinerU 解析完成，Markdown 长度: {len(md_content)}")

    # 优先解析 HTML 表格
    if "<table" in md_content:
        try:
            dfs = pd.read_html(md_content)
            if dfs:
                if len(dfs) == 1:
                    return dfs[0]
                main_cols = max(dfs, key=lambda d: len(d)).shape[1]
                same_structure = [df for df in dfs if df.shape[1] == main_cols and len(df) > 0]
                if same_structure:
                    return pd.concat(same_structure, ignore_index=True)
                return max(dfs, key=len)
        except Exception:
            pass

    # 再尝试 Markdown 表格
    tables = _extract_tables_from_markdown(md_content)
    if tables:
        all_dfs = []
        for table_lines in tables:
            df = _parse_markdown_table_lines(table_lines)
            if df is not None and not df.empty:
                all_dfs.append(df)
        if all_dfs:
            if len(all_dfs) == 1:
                return all_dfs[0]
            return pd.concat(all_dfs, ignore_index=True)

    # 返回文本
    lines = [l.strip() for l in md_content.splitlines() if l.strip() and not l.startswith("#")]
    if lines:
        return pd.DataFrame({"内容": lines})

    raise ValueError("MinerU 未提取到有效数据")


def _extract_tables_from_markdown(md_text):
    """从 Markdown 文本中提取所有表格"""
    tables = []
    current_table = []
    in_table = False

    for line in md_text.splitlines():
        if "|" in line and line.strip().startswith("|"):
            in_table = True
            current_table.append(line)
        else:
            if in_table and current_table:
                if len(current_table) >= 2:
                    tables.append(current_table)
                current_table = []
                in_table = False

    if current_table and len(current_table) >= 2:
        tables.append(current_table)

    return tables


def _parse_markdown_table_lines(lines):
    """解析 Markdown 表格行为 DataFrame"""
    if len(lines) < 2:
        return None

    headers = [c.strip() for c in lines[0].split("|") if c.strip()]

    data_lines = []
    for line in lines[1:]:
        cleaned = line.replace("|", "").replace("-", "").replace(":", "").strip()
        if not cleaned:
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if cells:
            data_lines.append(cells)

    if not data_lines:
        return None

    n_cols = len(headers)
    clean_rows = []
    for row in data_lines:
        if len(row) > n_cols:
            row = row[:n_cols]
        elif len(row) < n_cols:
            row = row + [""] * (n_cols - len(row))
        clean_rows.append(row)

    return pd.DataFrame(clean_rows, columns=headers)


def get_pdf_markdown(path, password=""):
    """获取 PDF 的 Markdown 文本（供布局转换使用）"""
    import pymupdf4llm
    import pymupdf

    doc = pymupdf.open(path)
    if doc.is_encrypted:
        doc.authenticate(password or "")
    md_text = pymupdf4llm.to_markdown(doc)
    doc.close()
    return md_text
