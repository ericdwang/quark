from ldap import MOD_ADD

from django.test import TestCase
from django.test.client import Client

from quark.auth.models import User
from quark.qldap import utils
from quark.settings import USERNAME_HELPTEXT


# TODO(flieee): Move tests over to test-only LDAP tree
class LDAPTestCase(TestCase):
    def setUp(self):
        self.user = 'test'
        self.new_user = 'testrename'
        self.password = 'stupidpassword'
        self.first_name = 'Silly'
        self.last_name = 'Test'
        self.group_of_names = 'test_group_of_names'
        self.posix_group = 'test_posix_group'
        utils.create_user(self.user, self.password, self.first_name,
                          self.last_name)
        User.objects.create_user(self.user)
        utils.create_group(self.group_of_names, object_class='groupOfNames')
        utils.create_group(self.posix_group, object_class='posixGroup')

    def tearDown(self):
        if utils.username_exists(self.user):
            utils.delete_user(self.user)
        if utils.username_exists(self.new_user):
            utils.delete_user(self.new_user)
        # TODO(flieee): this db reset should not be necessary,
        # but removing it causes DatabaseIntegrity errors
        User.objects.filter(username__in=[self.user, self.new_user]).delete()

        # Remove groups:
        utils.delete_group(self.group_of_names)
        self.assertFalse(utils.group_exists(self.group_of_names))

        utils.delete_group(self.posix_group)
        self.assertFalse(utils.group_exists(self.posix_group))

    def test_can_connect(self):
        bad_dn = 'cn=fakeldap,dc=tbp,dc=berkeley,dc=edu'
        bad_pw = 'stupidpassword'
        self.assertIsNone(utils.initialize(base_dn=bad_dn, base_pw=bad_pw))
        self.assertIsNotNone(utils.initialize())

    def test_create_new_user(self):
        self.assertFalse(utils.username_exists(self.new_user))
        self.assertTrue(utils.create_user(self.new_user, self.password,
                                          self.first_name, self.last_name))
        self.assertTrue(utils.username_exists(self.new_user))
        utils.delete_user(self.new_user)
        self.assertFalse(utils.username_exists(self.new_user))

    def test_username_exists(self):
        """Existing and non-existing users are identified correctly"""
        # New testing user exists
        self.assertTrue(utils.username_exists(self.user))
        # lit is a local user. It should not exist in TBP People group
        self.assertFalse(utils.username_exists('lit'))

    def test_create_existing_user(self):
        self.assertTrue(utils.username_exists(self.user))
        self.assertFalse(utils.create_user(self.user, self.password,
                                           self.first_name,
                                           self.last_name))

    def test_change_password(self):
        new_password = 'reallybadpassword'
        self.assertTrue(utils.check_password(self.user, self.password))
        self.assertTrue(utils.set_password(self.user, new_password))
        self.assertTrue(utils.check_password(self.user, new_password))

    def test_rename_user(self):
        invalid_name = (False, 'Invalid username. ' + USERNAME_HELPTEXT)
        correct = (True, 'User %s renamed to %s' % (self.user, self.new_user))
        self.assertTrue(User.objects.filter(username=self.user).exists())
        self.assertTrue(utils.username_exists(self.user))

        self.assertEqual(utils.rename_user(self.user, 'bad_username'),
                         invalid_name)
        # Nothing is changed
        self.assertTrue(User.objects.filter(username=self.user).exists())
        self.assertTrue(utils.username_exists(self.user))
        # Actual renaming
        self.assertEqual(utils.rename_user(self.user, self.new_user),
                         correct)

        self.assertFalse(User.objects.filter(username=self.user).exists())
        self.assertFalse(utils.username_exists(self.user))

        self.assertTrue(User.objects.filter(username=self.new_user).exists())
        self.assertTrue(utils.username_exists(self.new_user))

    def test_clear_group_of_names(self):
        self.assertTrue(utils.group_exists(self.group_of_names))
        # Ensure the there is only 1 member in the group (which should be the
        # default user), since this group is a groupOfNames object, requiring
        # at least 1 member):
        self.assertTrue(
            len(utils.get_group_members(self.group_of_names)) == 1)

        # Add the user to the group:
        self.assertTrue(utils.mod_user_group(
            self.user, self.group_of_names, action=MOD_ADD))
        # Ensure that there are now 2 members:
        self.assertTrue(
            len(utils.get_group_members(self.group_of_names)) == 2)

        # Clear the group (remove the user):
        self.assertTrue(utils.clear_group_members(self.group_of_names))
        # Group size should be 1 again, since default user should still be
        # left when clearing groupOfNames:
        self.assertTrue(
            len(utils.get_group_members(self.group_of_names)) == 1)

    def test_clear_posix_group(self):
        self.assertTrue(utils.group_exists(self.posix_group))
        # Ensure that there are no members in the group (posixGroup has no
        # minimum number of members, so there should be no members upon
        # creation of the group):
        self.assertTrue(len(utils.get_group_members(self.posix_group)) == 0)

        # Add the user to the group:
        self.assertTrue(utils.mod_user_group(
            self.user, self.posix_group, action=MOD_ADD))
        # Ensure that there is now 1 member:
        self.assertTrue(len(utils.get_group_members(self.posix_group)) == 1)

        # Clear the group (removes the user):
        self.assertTrue(utils.clear_group_members(self.posix_group))
        # Group size should be 0 again:
        self.assertTrue(len(utils.get_group_members(self.posix_group)) == 0)

    def test_valid_username_regex(self):
        # Valid name
        self.assertIsNotNone(utils.USERNAME_REGEX.match('zak'))
        # Too short
        self.assertIsNone(utils.USERNAME_REGEX.match('as'))
        # Too long
        str_len_31 = 'abcdefghijklmnopqrstuvwxyz01234'
        self.assertTrue(len(str_len_31) > 30)
        self.assertIsNone(utils.USERNAME_REGEX.match(str_len_31))
        # Number for first char
        self.assertIsNone(utils.USERNAME_REGEX.match('123'))

    def test_backend_auth(self):
        client = Client()
        self.assertTrue(client.login(username=self.user,
                                     password=self.password))
        self.assertFalse(client.login(username=self.user, password=''))
        self.assertFalse(client.login(username='superfakeuser', password=''))