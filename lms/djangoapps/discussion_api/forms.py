"""
Discussion API forms
"""
from django.core.exceptions import ValidationError
from django.forms import (
    BooleanField,
    CharField,
    Field,
    Form,
    IntegerField,
    MultipleHiddenInput,
    NullBooleanField,
)

from opaque_keys import InvalidKeyError
from opaque_keys.edx.locator import CourseLocator


class TopicIdField(Field):
    """
    Field for a list of topic_ids
    """
    widget = MultipleHiddenInput

    def validate(self, value):
        if value and "" in value:
            raise ValidationError("This field cannot be empty.")


class _PaginationForm(Form):
    """A form that includes pagination fields"""
    page = IntegerField(required=False, min_value=1)
    page_size = IntegerField(required=False, min_value=1)

    def clean_page(self):
        """Return given valid page or default of 1"""
        return self.cleaned_data.get("page") or 1

    def clean_page_size(self):
        """Return given valid page_size (capped at 100) or default of 10"""
        return min(self.cleaned_data.get("page_size") or 10, 100)


class ThreadListGetForm(_PaginationForm):
    """
    A form to validate query parameters in the thread list retrieval endpoint
    """
    course_id = CharField()
    topic_id = TopicIdField(required=False)

    def clean_course_id(self):
        """Validate course_id"""
        value = self.cleaned_data["course_id"]
        try:
            return CourseLocator.from_string(value)
        except InvalidKeyError:
            raise ValidationError("'{}' is not a valid course id".format(value))


class ThreadActionsForm(Form):
    """
    A form to handle fields in thread creation that require separate
    interactions with the comments service.
    """
    following = BooleanField(required=False)
    voted = BooleanField(required=False)


class CommentListGetForm(_PaginationForm):
    """
    A form to validate query parameters in the comment list retrieval endpoint
    """
    thread_id = CharField()
    # TODO: should we use something better here? This only accepts "True",
    # "False", "1", and "0"
    endorsed = NullBooleanField(required=False)
