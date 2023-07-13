from codedog.model import Change
from codedog.templates.template_cn import (
    CHANGE_SUMMARY,
    T3_TITLE_LINE,
    TABLE_LINE,
    TABLE_LINE_NODATA,
)


def generate_change_summary(changes: list[Change]) -> str:
    """format change summary

    Args:
        changes (list[Change]): pr changes and reviews
    Returns:
        str: format markdown table string of change summary
    """

    important_changes = []
    housekeeping_changes = []

    important_idx = 1
    housekeeping_idx = 1
    for change in changes:
        file_name = change.file_name or ""
        url = change.url or ""
        summary = change.summary or ""

        text = summary.replace("\n", "<br/>") if summary else ""
        text_template: str = TABLE_LINE.format(file_name=file_name, url=url, text=text)

        if not change.major:
            text = text_template.format(idx=important_idx)
            important_idx += 1
            important_changes.append(text)
        else:
            text = text_template.format(idx=housekeeping_idx)
            housekeeping_idx += 1
            housekeeping_changes.append(text)

    important_changes = "\n".join(important_changes) if important_changes else TABLE_LINE_NODATA
    housekeeping_changes = "\n".join(housekeeping_changes) if housekeeping_changes else TABLE_LINE_NODATA
    text = CHANGE_SUMMARY.format(important_changes=important_changes, housekeeping_changes=housekeeping_changes)
    return text


def generate_feedback(changes: list[Change]) -> str:
    """format feedback

    Args:
        changes (list[Change]): pr changes and reviews
    Returns:
        str: format markdown table string of feedback
    """
    texts = []

    idx = 1
    for change in changes:
        file_name = change.file_name
        url = change.url

        feedback = change.feedback
        if (
            not feedback
            or feedback in ("ok", "OK")
            or (len(feedback) < 30 and "ok" in feedback.lower())  # 移除ok + 其他短语的回复
        ):
            continue

        text = f"{T3_TITLE_LINE.format(idx=idx, file_name=file_name, url=url)}\n\n{feedback}"

        texts.append(text)
        idx += 1

    concat_feedback_text = "\n\n".join(texts) if texts else TABLE_LINE_NODATA
    return concat_feedback_text
