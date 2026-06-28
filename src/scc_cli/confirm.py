"""Case-insensitive confirmation prompt."""

from rich.prompt import Confirm as RichConfirm


class Confirm(RichConfirm):
    """Case-insensitive confirmation prompt.

    Rich's default Confirm only accepts lowercase y/n but shows
    "Please enter Y or N" error message, which is confusing.
    This subclass accepts both cases.
    """

    def check_choice(self, value: str) -> bool:
        """Check if value is a valid yes/no choice (case-insensitive)."""
        return value.strip().lower() in self.choices
