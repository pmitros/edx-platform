"""
Tests for Discussion API serializers
"""
import itertools
from urlparse import urlparse

import ddt
import httpretty
import mock

from django.test.client import RequestFactory

from discussion_api.serializers import CommentSerializer, ThreadSerializer, get_context
from discussion_api.tests.utils import (
    CommentsServiceMockMixin,
    make_minimal_cs_thread,
    make_minimal_cs_comment,
)
from django_comment_common.models import (
    FORUM_ROLE_ADMINISTRATOR,
    FORUM_ROLE_COMMUNITY_TA,
    FORUM_ROLE_MODERATOR,
    FORUM_ROLE_STUDENT,
    Role,
)
from lms.lib.comment_client.comment import Comment
from lms.lib.comment_client.thread import Thread
from student.tests.factories import UserFactory
from util.testing import UrlResetMixin
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from openedx.core.djangoapps.course_groups.tests.helpers import CohortFactory


@ddt.ddt
class SerializerTestMixin(CommentsServiceMockMixin, UrlResetMixin):
    @mock.patch.dict("django.conf.settings.FEATURES", {"ENABLE_DISCUSSION_SERVICE": True})
    def setUp(self):
        super(SerializerTestMixin, self).setUp()
        httpretty.reset()
        httpretty.enable()
        self.addCleanup(httpretty.disable)
        self.maxDiff = None  # pylint: disable=invalid-name
        self.user = UserFactory.create()
        self.register_get_user_response(self.user)
        self.request = RequestFactory().get("/dummy")
        self.request.user = self.user
        self.course = CourseFactory.create()
        self.author = UserFactory.create()

    def create_role(self, role_name, users, course=None):
        """Create a Role in self.course with the given name and users"""
        course = course or self.course
        role = Role.objects.create(name=role_name, course_id=course.id)
        role.users = users

    @ddt.data(
        (FORUM_ROLE_ADMINISTRATOR, True, False, True),
        (FORUM_ROLE_ADMINISTRATOR, False, True, False),
        (FORUM_ROLE_MODERATOR, True, False, True),
        (FORUM_ROLE_MODERATOR, False, True, False),
        (FORUM_ROLE_COMMUNITY_TA, True, False, True),
        (FORUM_ROLE_COMMUNITY_TA, False, True, False),
        (FORUM_ROLE_STUDENT, True, False, True),
        (FORUM_ROLE_STUDENT, False, True, True),
    )
    @ddt.unpack
    def test_anonymity(self, role_name, anonymous, anonymous_to_peers, expected_serialized_anonymous):
        """
        Test that content is properly made anonymous.

        Content should be anonymous iff the anonymous field is true or the
        anonymous_to_peers field is true and the requester does not have a
        privileged role.

        role_name is the name of the requester's role.
        anonymous is the value of the anonymous field in the content.
        anonymous_to_peers is the value of the anonymous_to_peers field in the
          content.
        expected_serialized_anonymous is whether the content should actually be
          anonymous in the API output when requested by a user with the given
          role.
        """
        self.create_role(role_name, [self.user])
        serialized = self.serialize(
            self.make_cs_content({"anonymous": anonymous, "anonymous_to_peers": anonymous_to_peers})
        )
        actual_serialized_anonymous = serialized["author"] is None
        self.assertEqual(actual_serialized_anonymous, expected_serialized_anonymous)

    @ddt.data(
        (FORUM_ROLE_ADMINISTRATOR, False, "staff"),
        (FORUM_ROLE_ADMINISTRATOR, True, None),
        (FORUM_ROLE_MODERATOR, False, "staff"),
        (FORUM_ROLE_MODERATOR, True, None),
        (FORUM_ROLE_COMMUNITY_TA, False, "community_ta"),
        (FORUM_ROLE_COMMUNITY_TA, True, None),
        (FORUM_ROLE_STUDENT, False, None),
        (FORUM_ROLE_STUDENT, True, None),
    )
    @ddt.unpack
    def test_author_labels(self, role_name, anonymous, expected_label):
        """
        Test correctness of the author_label field.

        The label should be "staff", "staff", or "community_ta" for the
        Administrator, Moderator, and Community TA roles, respectively, but
        the label should not be present if the content is anonymous.

        role_name is the name of the author's role.
        anonymous is the value of the anonymous field in the content.
        expected_label is the expected value of the author_label field in the
          API output.
        """
        self.create_role(role_name, [self.author])
        serialized = self.serialize(self.make_cs_content({"anonymous": anonymous}))
        self.assertEqual(serialized["author_label"], expected_label)

    def test_abuse_flagged(self):
        serialized = self.serialize(self.make_cs_content({"abuse_flaggers": [str(self.user.id)]}))
        self.assertEqual(serialized["abuse_flagged"], True)

    def test_voted(self):
        thread_id = "test_thread"
        self.register_get_user_response(self.user, upvoted_ids=[thread_id])
        serialized = self.serialize(self.make_cs_content({"id": thread_id}))
        self.assertEqual(serialized["voted"], True)


@ddt.ddt
class ThreadSerializerSerializationTest(SerializerTestMixin, ModuleStoreTestCase):
    """Tests for ThreadSerializer serialization."""
    def make_cs_content(self, overrides):
        """
        Create a thread with the given overrides, plus some useful test data.
        """
        merged_overrides = {
            "course_id": unicode(self.course.id),
            "user_id": str(self.author.id),
            "username": self.author.username,
        }
        merged_overrides.update(overrides)
        return make_minimal_cs_thread(merged_overrides)

    def serialize(self, thread):
        """
        Create a serializer with an appropriate context and use it to serialize
        the given thread, returning the result.
        """
        return ThreadSerializer(thread, context=get_context(self.course, self.request)).data

    def test_basic(self):
        thread = {
            "id": "test_thread",
            "course_id": unicode(self.course.id),
            "commentable_id": "test_topic",
            "group_id": None,
            "user_id": str(self.author.id),
            "username": self.author.username,
            "anonymous": False,
            "anonymous_to_peers": False,
            "created_at": "2015-04-28T00:00:00Z",
            "updated_at": "2015-04-28T11:11:11Z",
            "thread_type": "discussion",
            "title": "Test Title",
            "body": "Test body",
            "pinned": True,
            "closed": False,
            "abuse_flaggers": [],
            "votes": {"up_count": 4},
            "comments_count": 5,
            "unread_comments_count": 3,
        }
        expected = {
            "id": "test_thread",
            "course_id": unicode(self.course.id),
            "topic_id": "test_topic",
            "group_id": None,
            "group_name": None,
            "author": self.author.username,
            "author_label": None,
            "created_at": "2015-04-28T00:00:00Z",
            "updated_at": "2015-04-28T11:11:11Z",
            "type": "discussion",
            "title": "Test Title",
            "raw_body": "Test body",
            "pinned": True,
            "closed": False,
            "following": False,
            "abuse_flagged": False,
            "voted": False,
            "vote_count": 4,
            "comment_count": 5,
            "unread_comment_count": 3,
            "comment_list_url": "http://testserver/api/discussion/v1/comments/?thread_id=test_thread",
            "endorsed_comment_list_url": None,
            "non_endorsed_comment_list_url": None,
        }
        self.assertEqual(self.serialize(thread), expected)

        thread["thread_type"] = "question"
        expected.update({
            "type": "question",
            "comment_list_url": None,
            "endorsed_comment_list_url": (
                "http://testserver/api/discussion/v1/comments/?thread_id=test_thread&endorsed=True"
            ),
            "non_endorsed_comment_list_url": (
                "http://testserver/api/discussion/v1/comments/?thread_id=test_thread&endorsed=False"
            ),
        })
        self.assertEqual(self.serialize(thread), expected)

    def test_group(self):
        cohort = CohortFactory.create(course_id=self.course.id)
        serialized = self.serialize(self.make_cs_content({"group_id": cohort.id}))
        self.assertEqual(serialized["group_id"], cohort.id)
        self.assertEqual(serialized["group_name"], cohort.name)

    def test_following(self):
        thread_id = "test_thread"
        self.register_get_user_response(self.user, subscribed_thread_ids=[thread_id])
        serialized = self.serialize(self.make_cs_content({"id": thread_id}))
        self.assertEqual(serialized["following"], True)


@ddt.ddt
class CommentSerializerTest(SerializerTestMixin, ModuleStoreTestCase):
    """Tests for CommentSerializer."""
    def setUp(self):
        super(CommentSerializerTest, self).setUp()
        self.endorser = UserFactory.create()
        self.endorsed_at = "2015-05-18T12:34:56Z"

    def make_cs_content(self, overrides=None, with_endorsement=False):
        """
        Create a comment with the given overrides, plus some useful test data.
        """
        merged_overrides = {
            "user_id": str(self.author.id),
            "username": self.author.username
        }
        if with_endorsement:
            merged_overrides["endorsement"] = {
                "user_id": str(self.endorser.id),
                "time": self.endorsed_at
            }
        merged_overrides.update(overrides or {})
        return make_minimal_cs_comment(merged_overrides)

    def serialize(self, comment, thread_data=None):
        """
        Create a serializer with an appropriate context and use it to serialize
        the given comment, returning the result.
        """
        context = get_context(self.course, self.request, make_minimal_cs_thread(thread_data))
        return CommentSerializer(comment, context=context).data

    def test_basic(self):
        comment = {
            "id": "test_comment",
            "thread_id": "test_thread",
            "user_id": str(self.author.id),
            "username": self.author.username,
            "anonymous": False,
            "anonymous_to_peers": False,
            "created_at": "2015-04-28T00:00:00Z",
            "updated_at": "2015-04-28T11:11:11Z",
            "body": "Test body",
            "endorsed": False,
            "abuse_flaggers": [],
            "votes": {"up_count": 4},
            "children": [],
        }
        expected = {
            "id": "test_comment",
            "thread_id": "test_thread",
            "parent_id": None,
            "author": self.author.username,
            "author_label": None,
            "created_at": "2015-04-28T00:00:00Z",
            "updated_at": "2015-04-28T11:11:11Z",
            "raw_body": "Test body",
            "endorsed": False,
            "endorsed_by": None,
            "endorsed_by_label": None,
            "endorsed_at": None,
            "abuse_flagged": False,
            "voted": False,
            "vote_count": 4,
            "children": [],
        }
        self.assertEqual(self.serialize(comment), expected)

    @ddt.data(
        *itertools.product(
            [
                FORUM_ROLE_ADMINISTRATOR,
                FORUM_ROLE_MODERATOR,
                FORUM_ROLE_COMMUNITY_TA,
                FORUM_ROLE_STUDENT,
            ],
            [True, False]
        )
    )
    @ddt.unpack
    def test_endorsed_by(self, endorser_role_name, thread_anonymous):
        """
        Test correctness of the endorsed_by field.

        The endorser should be anonymous iff the thread is anonymous to the
        requester, and the endorser is not a privileged user.

        endorser_role_name is the name of the endorser's role.
        thread_anonymous is the value of the anonymous field in the thread.
        """
        self.create_role(endorser_role_name, [self.endorser])
        serialized = self.serialize(
            self.make_cs_content(with_endorsement=True),
            thread_data={"anonymous": thread_anonymous}
        )
        actual_endorser_anonymous = serialized["endorsed_by"] is None
        expected_endorser_anonymous = endorser_role_name == FORUM_ROLE_STUDENT and thread_anonymous
        self.assertEqual(actual_endorser_anonymous, expected_endorser_anonymous)

    @ddt.data(
        (FORUM_ROLE_ADMINISTRATOR, "staff"),
        (FORUM_ROLE_MODERATOR, "staff"),
        (FORUM_ROLE_COMMUNITY_TA, "community_ta"),
        (FORUM_ROLE_STUDENT, None),
    )
    @ddt.unpack
    def test_endorsed_by_labels(self, role_name, expected_label):
        """
        Test correctness of the endorsed_by_label field.

        The label should be "staff", "staff", or "community_ta" for the
        Administrator, Moderator, and Community TA roles, respectively.

        role_name is the name of the author's role.
        expected_label is the expected value of the author_label field in the
          API output.
        """
        self.create_role(role_name, [self.endorser])
        serialized = self.serialize(self.make_cs_content(with_endorsement=True))
        self.assertEqual(serialized["endorsed_by_label"], expected_label)

    def test_endorsed_at(self):
        serialized = self.serialize(self.make_cs_content(with_endorsement=True))
        self.assertEqual(serialized["endorsed_at"], self.endorsed_at)

    def test_children(self):
        comment = self.make_cs_content({
            "id": "test_root",
            "children": [
                self.make_cs_content({
                    "id": "test_child_1",
                }),
                self.make_cs_content({
                    "id": "test_child_2",
                    "children": [self.make_cs_content({"id": "test_grandchild"})],
                }),
            ],
        })
        serialized = self.serialize(comment)
        self.assertEqual(serialized["children"][0]["id"], "test_child_1")
        self.assertEqual(serialized["children"][0]["parent_id"], "test_root")
        self.assertEqual(serialized["children"][1]["id"], "test_child_2")
        self.assertEqual(serialized["children"][1]["parent_id"], "test_root")
        self.assertEqual(serialized["children"][1]["children"][0]["id"], "test_grandchild")
        self.assertEqual(serialized["children"][1]["children"][0]["parent_id"], "test_child_2")


@ddt.ddt
class ThreadSerializerDeserializationTest(CommentsServiceMockMixin, UrlResetMixin, ModuleStoreTestCase):
    """Tests for ThreadSerializer deserialization."""
    @mock.patch.dict("django.conf.settings.FEATURES", {"ENABLE_DISCUSSION_SERVICE": True})
    def setUp(self):
        super(ThreadSerializerDeserializationTest, self).setUp()
        httpretty.reset()
        httpretty.enable()
        self.addCleanup(httpretty.disable)
        self.course = CourseFactory.create()
        self.user = UserFactory.create()
        self.register_get_user_response(self.user)
        self.request = RequestFactory().get("/dummy")
        self.request.user = self.user
        self.minimal_data = {
            "course_id": unicode(self.course.id),
            "topic_id": "test_topic",
            "type": "discussion",
            "title": "Test Title",
            "raw_body": "Test body",
        }
        self.existing_thread = Thread(**make_minimal_cs_thread({
            "id": "existing_thread",
            "course_id": unicode(self.course.id),
            "commentable_id": "original_topic",
            "thread_type": "discussion",
            "title": "Original Title",
            "body": "Original body",
            "user_id": str(self.user.id),
        }))

    def save_and_reserialize(self, data, instance=None):
        """
        Create a serializer with the given data and (if updating) instance,
        ensure that it is valid, save the result, and return the full thread
        data from the serializer.
        """
        serializer = ThreadSerializer(
            instance,
            data=data,
            partial=(instance is not None),
            context=get_context(self.course, self.request)
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()
        return serializer.data

    def test_create_minimal(self):
        self.register_post_thread_response({"id": "test_id"})
        saved = self.save_and_reserialize(self.minimal_data)
        self.assertEqual(
            urlparse(httpretty.last_request().path).path,
            "/api/v1/test_topic/threads"
        )
        self.assertEqual(
            httpretty.last_request().parsed_body,
            {
                "course_id": [unicode(self.course.id)],
                "commentable_id": ["test_topic"],
                "thread_type": ["discussion"],
                "title": ["Test Title"],
                "body": ["Test body"],
                "user_id": [str(self.user.id)],
            }
        )
        self.assertEqual(saved["id"], "test_id")

    def test_create_missing_field(self):
        for field in self.minimal_data:
            data = self.minimal_data.copy()
            data.pop(field)
            serializer = ThreadSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertEqual(
                serializer.errors,
                {field: ["This field is required."]}
            )

    def test_create_type(self):
        self.register_post_thread_response({"id": "test_id"})
        data = self.minimal_data.copy()
        data["type"] = "question"
        self.save_and_reserialize(data)

        data["type"] = "invalid_type"
        serializer = ThreadSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_update_empty(self):
        self.register_put_thread_response(self.existing_thread.attributes)
        self.save_and_reserialize({}, self.existing_thread)
        self.assertEqual(
            httpretty.last_request().parsed_body,
            {
                "course_id": [unicode(self.course.id)],
                "commentable_id": ["original_topic"],
                "thread_type": ["discussion"],
                "title": ["Original Title"],
                "body": ["Original body"],
                "anonymous": ["False"],
                "anonymous_to_peers": ["False"],
                "closed": ["False"],
                "pinned": ["False"],
                "user_id": [str(self.user.id)],
            }
        )

    def test_update_all(self):
        self.register_put_thread_response(self.existing_thread.attributes)
        data = {
            "topic_id": "edited_topic",
            "type": "question",
            "title": "Edited Title",
            "raw_body": "Edited body",
        }
        saved = self.save_and_reserialize(data, self.existing_thread)
        self.assertEqual(
            httpretty.last_request().parsed_body,
            {
                "course_id": [unicode(self.course.id)],
                "commentable_id": ["edited_topic"],
                "thread_type": ["question"],
                "title": ["Edited Title"],
                "body": ["Edited body"],
                "anonymous": ["False"],
                "anonymous_to_peers": ["False"],
                "closed": ["False"],
                "pinned": ["False"],
                "user_id": [str(self.user.id)],
            }
        )
        for key in data:
            self.assertEqual(saved[key], data[key])

    def test_update_empty_string(self):
        serializer = ThreadSerializer(
            self.existing_thread,
            data={field: "" for field in ["topic_id", "title", "raw_body"]},
            partial=True,
            context=get_context(self.course, self.request)
        )
        self.assertEqual(
            serializer.errors,
            {field: ["This field is required."] for field in ["topic_id", "title", "raw_body"]}
        )

    def test_update_course_id(self):
        serializer = ThreadSerializer(
            self.existing_thread,
            data={"course_id": "some/other/course"},
            partial=True,
            context=get_context(self.course, self.request)
        )
        self.assertEqual(
            serializer.errors,
            {"course_id": ["This field is not allowed in an update."]}
        )


@ddt.ddt
class CommentSerializerDeserializationTest(CommentsServiceMockMixin, ModuleStoreTestCase):
    """Tests for ThreadSerializer deserialization."""
    def setUp(self):
        super(CommentSerializerDeserializationTest, self).setUp()
        httpretty.reset()
        httpretty.enable()
        self.addCleanup(httpretty.disable)
        self.course = CourseFactory.create()
        self.user = UserFactory.create()
        self.register_get_user_response(self.user)
        self.request = RequestFactory().get("/dummy")
        self.request.user = self.user
        self.minimal_data = {
            "thread_id": "test_thread",
            "raw_body": "Test body",
        }
        self.existing_comment = Comment(**make_minimal_cs_comment({
            "id": "existing_comment",
            "thread_id": "existing_thread",
            "body": "Original body",
            "user_id": str(self.user.id),
            "course_id": unicode(self.course.id),
        }))

    def save_and_reserialize(self, data, parent_id=None, instance=None):
        """
        Create a serializer with the given data, ensure that it is valid, save
        the result, and return the full comment data from the serializer.
        """
        context = get_context(
            self.course,
            self.request,
            make_minimal_cs_thread({"course_id": unicode(self.course.id)}),
            parent_id
        )
        serializer = CommentSerializer(
            instance,
            data=data,
            partial=(instance is not None),
            context=context
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()
        return serializer.data

    @ddt.data(None, "test_parent")
    def test_create_success(self, parent_id):
        if parent_id:
            self.register_get_comment_response({"thread_id": "test_thread", "id": parent_id})
        self.register_post_comment_response(
            {"id": "test_comment"},
            thread_id=(None if parent_id else "test_thread"),
            parent_id=parent_id
        )
        saved = self.save_and_reserialize(self.minimal_data, parent_id=parent_id)
        expected_url = (
            "/api/v1/comments/{}".format(parent_id) if parent_id else
            "/api/v1/threads/test_thread/comments"
        )
        self.assertEqual(urlparse(httpretty.last_request().path).path, expected_url)
        self.assertEqual(
            httpretty.last_request().parsed_body,
            {
                "course_id": [unicode(self.course.id)],
                "body": ["Test body"],
                "user_id": [str(self.user.id)],
            }
        )
        self.assertEqual(saved["id"], "test_comment")
        self.assertEqual(saved["parent_id"], parent_id)

    def test_create_parent_id_nonexistent(self):
        self.register_get_comment_error_response("bad_parent", 404)
        context = get_context(self.course, self.request, make_minimal_cs_thread(), "bad_parent")
        serializer = CommentSerializer(data=self.minimal_data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors,
            {
                "non_field_errors": [
                    "parent_id does not identify a comment in the thread identified by thread_id."
                ]
            }
        )

    def test_create_parent_id_wrong_thread(self):
        self.register_get_comment_response({"thread_id": "different_thread", "id": "test_parent"})
        context = get_context(self.course, self.request, make_minimal_cs_thread(), "test_parent")
        serializer = CommentSerializer(data=self.minimal_data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors,
            {
                "non_field_errors": [
                    "parent_id does not identify a comment in the thread identified by thread_id."
                ]
            }
        )

    def test_create_missing_field(self):
        for field in self.minimal_data:
            data = self.minimal_data.copy()
            data.pop(field)
            serializer = CommentSerializer(
                data=data,
                context=get_context(self.course, self.request, make_minimal_cs_thread())
            )
            self.assertFalse(serializer.is_valid())
            self.assertEqual(
                serializer.errors,
                {field: ["This field is required."]}
            )

    def test_update_empty(self):
        self.register_put_comment_response(self.existing_comment.attributes)
        self.save_and_reserialize({}, instance=self.existing_comment)
        self.assertEqual(
            httpretty.last_request().parsed_body,
            {
                "body": ["Original body"],
                "course_id": [unicode(self.course.id)],
                "user_id": [str(self.user.id)],
                "anonymous": ["False"],
                "anonymous_to_peers": ["False"],
                "endorsed": ["False"],
            }
        )

    def test_update_all(self):
        self.register_put_comment_response(self.existing_comment.attributes)
        data = {"raw_body": "Edited body"}
        saved = self.save_and_reserialize(data, instance=self.existing_comment)
        self.assertEqual(
            httpretty.last_request().parsed_body,
            {
                "body": ["Edited body"],
                "course_id": [unicode(self.course.id)],
                "user_id": [str(self.user.id)],
                "anonymous": ["False"],
                "anonymous_to_peers": ["False"],
                "endorsed": ["False"],
            }
        )
        self.assertEqual(saved["raw_body"], data["raw_body"])

    def test_update_empty_raw_body(self):
        serializer = CommentSerializer(
            self.existing_comment,
            data={"raw_body": ""},
            partial=True,
            context=get_context(self.course, self.request)
        )
        self.assertEqual(
            serializer.errors,
            {"raw_body": ["This field is required."]}
        )

    def test_update_thread_id(self):
        serializer = CommentSerializer(
            self.existing_comment,
            data={"thread_id": "different_thread"},
            partial=True,
            context=get_context(self.course, self.request)
        )
        self.assertEqual(
            serializer.errors,
            {"thread_id": ["This field is not allowed in an update."]}
        )
