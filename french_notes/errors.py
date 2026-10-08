"""Structured application errors, independent of the interface language."""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from .core import SaveResult


ERROR_MESSAGES = {
    "content_text_required": {
        "fr": "Le contenu en français doit être du texte.",
        "en": "French content must be text.",
        "zh": "法语内容必须是文字。",
    },
    "unsupported_control": {
        "fr": "Le contenu contient des caractères de contrôle non pris en charge. Supprimez-les, puis réessayez.",
        "en": "The content contains unsupported control characters. Remove them and try again.",
        "zh": "内容包含不支持的控制字符，请删除后重试。",
    },
    "content_empty": {
        "fr": "Le contenu en français ne peut pas être vide.",
        "en": "French content cannot be empty.",
        "zh": "法语内容不能为空。",
    },
    "letter_required": {
        "fr": "Chaque note doit contenir au moins une lettre ; les nombres ou la ponctuation seuls ne suffisent pas.",
        "en": "Each note must contain at least one letter; numbers or punctuation alone are not enough.",
        "zh": "每条笔记至少需要一个字母，不能只有数字或标点。",
    },
    "csv_symlink": {
        "fr": "Le chemin du CSV est un lien symbolique. Sélectionnez le fichier CSV réel.",
        "en": "The CSV path is a symbolic link. Select the actual CSV file.",
        "zh": "CSV 路径是符号链接，请选择实际的 CSV 文件。",
    },
    "csv_changed_during_read": {
        "fr": "Le fichier CSV a changé pendant sa lecture. Actualisez l'aperçu, puis réessayez.",
        "en": "The CSV changed while it was being read. Refresh the preview and try again.",
        "zh": "CSV 在读取期间发生变化，请重新分析后重试。",
    },
    "csv_read_failed": {
        "fr": "Impossible de lire le fichier CSV : {detail}",
        "en": "Unable to read the CSV file: {detail}",
        "zh": "无法读取 CSV 文件：{detail}",
    },
    "csv_encoding": {
        "fr": "L'encodage du CSV est invalide. Enregistrez le fichier en UTF-8. Le fichier d'origine n'a pas été modifié.",
        "en": "The CSV encoding is invalid. Save the file as UTF-8. The original file has not been changed.",
        "zh": "CSV 编码无效，请使用 UTF-8 编码保存文件；原文件未修改。",
    },
    "csv_header": {
        "fr": "L'en-tête du CSV doit contenir, dans cet ordre : id,category,french,created_at. Le fichier d'origine n'a pas été modifié.",
        "en": "The CSV header must contain, in this order: id,category,french,created_at. The original file has not been changed.",
        "zh": "CSV 表头必须依次为 id,category,french,created_at；原文件未修改。",
    },
    "csv_field_count": {
        "fr": "Ligne {line} du CSV : nombre de champs incorrect (4 champs attendus). Le fichier d'origine n'a pas été modifié.",
        "en": "CSV line {line}: incorrect field count (4 fields required). The original file has not been changed.",
        "zh": "CSV 第 {line} 行字段数量错误，应有 4 个字段；原文件未修改。",
    },
    "uuid_format": {
        "fr": "L'identifiant doit être un UUID au format standard, en minuscules.",
        "en": "The identifier must be a standard lowercase UUID.",
        "zh": "标识符必须是标准格式的小写 UUID。",
    },
    "duplicate_uuid": {
        "fr": "Un identifiant est présent plusieurs fois.",
        "en": "An identifier occurs more than once.",
        "zh": "存在重复的标识符。",
    },
    "category_invalid": {
        "fr": "La catégorie doit être « word » ou « sentence ».",
        "en": "The category must be 'word' or 'sentence'.",
        "zh": "分类必须为 word 或 sentence。",
    },
    "iso_datetime_required": {
        "fr": "La date de création doit inclure une date et une heure au format ISO.",
        "en": "The creation timestamp must include a date and time in ISO format.",
        "zh": "创建时间必须包含 ISO 格式的日期和时间。",
    },
    "csv_row_invalid": {
        "fr": "Ligne {line} du CSV : données invalides. {detail} Le fichier d'origine n'a pas été modifié.",
        "en": "CSV line {line}: invalid data. {detail} The original file has not been changed.",
        "zh": "CSV 第 {line} 行内容无效：{detail} 原文件未修改。",
    },
    "csv_malformed": {
        "fr": "Le CSV est mal formé : {detail}. Le fichier d'origine n'a pas été modifié.",
        "en": "The CSV is malformed: {detail}. The original file has not been changed.",
        "zh": "CSV 格式损坏：{detail}；原文件未修改。",
    },
    "input_text_required": {
        "fr": "La saisie doit être du texte.",
        "en": "The input must be text.",
        "zh": "输入内容必须是文字。",
    },
    "input_line_invalid": {
        "fr": "Ligne {line} de la saisie : contenu invalide. {detail}",
        "en": "Input line {line}: invalid content. {detail}",
        "zh": "输入第 {line} 行内容无效：{detail}",
    },
    "csv_external_change": {
        "fr": "Le fichier CSV a été modifié par un autre programme. Enregistrement annulé. Actualisez l'aperçu, puis réessayez.",
        "en": "The CSV was changed by another program. Saving was cancelled. Refresh the preview and try again.",
        "zh": "CSV 已被其他程序修改，保存已取消；请重新分析后重试。",
    },
    "csv_lock_exists": {
        "fr": "Le fichier CSV est en cours d'enregistrement par une autre instance. Fermez les autres instances, puis réessayez. Si l'application s'est arrêtée de façon inattendue, vérifiez qu'aucun enregistrement n'est en cours avant de supprimer manuellement le fichier de verrouillage : {path}",
        "en": "Another instance is saving this CSV. Close the other instances and try again. If the application stopped unexpectedly, make sure no save is in progress before manually deleting the lock file: {path}",
        "zh": "另一个实例正在保存此 CSV，请关闭其他实例后重试。若上次程序意外退出，请确认没有程序正在保存，再手动删除锁文件：{path}",
    },
    "csv_save_failed": {
        "fr": "Impossible d'enregistrer le fichier CSV : {detail}",
        "en": "Unable to save the CSV file: {detail}",
        "zh": "无法保存 CSV 文件：{detail}",
    },
    "save_outcome_failed": {
        "fr": "L'enregistrement n'a pas abouti",
        "en": "Saving did not complete",
        "zh": "保存未完成",
    },
    "save_outcome_saved": {
        "fr": "Les notes ont été enregistrées dans le CSV",
        "en": "The notes have been saved in the CSV",
        "zh": "笔记已保存到 CSV",
    },
    "save_outcome_noop": {
        "fr": "Aucune nouvelle note n'a été ajoutée ; le CSV n'a pas été modifié",
        "en": "No new notes were added; the CSV has not been changed",
        "zh": "未新增笔记，CSV 未修改",
    },
    "csv_lock_changed": {
        "fr": "{outcome}, mais le fichier de verrouillage a été modifié par un autre programme et n'a pas été supprimé automatiquement. Assurez-vous qu'aucun programme n'enregistre ce CSV, puis vérifiez ce fichier : {path}",
        "en": "{outcome}, but another program changed the lock file, so it was not deleted automatically. Make sure no program is saving this CSV, then check this file: {path}",
        "zh": "{outcome}，但锁文件已被其他程序修改，未自动删除。请确认没有程序正在保存此 CSV，再检查该文件：{path}",
    },
    "csv_lock_cleanup": {
        "fr": "{outcome}, mais le fichier de verrouillage ne peut pas être supprimé : {path}. Vérifiez qu'aucun programme n'enregistre ce CSV avant de le supprimer manuellement. Détail : {detail}",
        "en": "{outcome}, but the lock file could not be deleted: {path}. Make sure no program is saving this CSV before deleting it manually. Details: {detail}",
        "zh": "{outcome}，但无法删除锁文件：{path}。请确认没有程序正在保存此 CSV，再手动删除。详细信息：{detail}",
    },
    "additional_problem": {
        "fr": "Autre problème : {detail}",
        "en": "Additional problem: {detail}",
        "zh": "另一个问题：{detail}",
    },
    "preview_required": {
        "fr": "Les données à enregistrer doivent provenir de l'aperçu des notes.",
        "en": "Notes to save must come from the note preview.",
        "zh": "待保存内容必须来自笔记预览。",
    },
    "preview_status": {
        "fr": "L'état de l'aperçu est invalide. Actualisez l'aperçu avant d'enregistrer.",
        "en": "The preview status is invalid. Refresh the preview before saving.",
        "zh": "预览状态无效，请重新分析后保存。",
    },
    "note_category_invalid": {
        "fr": "La catégorie de la note doit être « word » ou « sentence ».",
        "en": "The note category must be 'word' or 'sentence'.",
        "zh": "笔记分类必须为 word 或 sentence。",
    },
    "csv_backup_cleanup": {
        "fr": "Les notes ont été enregistrées dans le CSV, mais l'ancienne sauvegarde n'a pas pu être supprimée : {path}. Détail : {detail}",
        "en": "The notes have been saved in the CSV, but the old backup could not be deleted: {path}. Details: {detail}",
        "zh": "笔记已保存到 CSV，但无法删除旧备份：{path}。详细信息：{detail}",
    },
}


def _render(key: str, params: Mapping[str, object], language: str) -> str:
    language = language if language in ("zh", "en", "fr") else "fr"
    rendered = {}
    for name, value in params.items():
        localise = getattr(value, "localized_message", None)
        rendered[name] = localise(language) if callable(localise) else value
    return ERROR_MESSAGES[key][language].format(**rendered)


class Message:
    """A translatable fragment used inside a structured error."""

    def __init__(self, key: str, params: Mapping[str, object] | None = None):
        self.key = key
        self.params = dict(params or {})

    def localized_message(self, language: str) -> str:
        return _render(self.key, self.params, language)

    def __str__(self) -> str:
        return self.localized_message("fr")


class _LocalizedError:
    key: str | None
    params: dict[str, object]

    def _configure(
        self, message: str | None, key: str | None, params: Mapping[str, object] | None
    ) -> str:
        self.key = key
        self.params = dict(params or {})
        self._literal_message = message or ""
        self.additional_problems: list[Message | _LocalizedError] = []
        return self.localized_message("fr")

    def localized_message(self, language: str) -> str:
        text = _render(self.key, self.params, language) if self.key else self._literal_message
        for problem in self.additional_problems:
            text += "\n" + _render("additional_problem", {"detail": problem}, language)
        return text

    def add_problem(self, problem: Message | _LocalizedError) -> None:
        self.additional_problems.append(problem)
        # Exception.args remains a complete French diagnostic for existing
        # callers.  The structured version can render every nested message.
        self.args = (self.localized_message("fr"),)


class StoreError(_LocalizedError, Exception):
    """A storage error, optionally carrying the already committed result."""

    def __init__(
        self,
        message: str | None = None,
        *,
        key: str | None = None,
        params: Mapping[str, object] | None = None,
        saved_result: SaveResult | None = None,
    ):
        super().__init__(self._configure(message, key, params))
        self.saved_result = saved_result


class ValidationError(_LocalizedError, ValueError):
    """A translatable validation failure compatible with ValueError handlers."""

    def __init__(
        self,
        message: str | None = None,
        *,
        key: str | None = None,
        params: Mapping[str, object] | None = None,
    ):
        super().__init__(self._configure(message, key, params))
