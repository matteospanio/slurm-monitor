"""A small modal confirmation helper used before destructive actions."""

from typing import Optional

from PySide6.QtWidgets import QMessageBox, QWidget


def confirm(
    parent: Optional[QWidget],
    title: str,
    text: str,
    *,
    dangerous: bool = False,
    confirm_label: str = "OK",
) -> bool:
    """Show a modal yes/no dialog; return True if the user confirmed."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(
        QMessageBox.Icon.Warning if dangerous else QMessageBox.Icon.Question
    )
    accept = box.addButton(confirm_label, QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)
    box.exec()
    return box.clickedButton() is accept
