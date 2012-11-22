import datetime
import mox

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import make_aware

from quark.base_pie.models import School
from quark.base_pie.models import Season


class SeasonManagerTest(TestCase):
    def assertSeasonEquals(self, season, year, start, end):
        self.assertEquals(season.year, year)
        self.assertEquals(season.start_date, start)
        self.assertEquals(season.end_date, end)

    def assertSeasonSaved(self, season):
        # Check if an object matching this Season exists in the database. Django
        # doesn't have a good way of actually checking this, so the best we can
        # do is verify that an object with all the same fields set to the same
        # values exists in the database.
        self.assertTrue(
            Season.objects.filter(pk=season.pk,
                                  year=season.year,
                                  start_date=season.start_date,
                                  end_date=season.end_date).exists())

    def assertSeasonNotSaved(self, season):
        # Reverse of the above.
        self.assertFalse(
            Season.objects.filter(pk=season.pk,
                                  year=season.year,
                                  start_date=season.start_date,
                                  end_date=season.end_date).exists())

    def setUp(self):
        self.mox = mox.Mox()
        self.tz = timezone.get_current_timezone()

    def tearDown(self):
        self.mox.UnsetStubs()

    def test_create_nonexisting_season(self):
        # Make sure a valid season is saved properly
        date = make_aware(datetime.datetime(2012, 02, 01), self.tz)
        season = Season.objects.get_current_season(date)
        self.assertSeasonSaved(season)

        start, end = Season.objects.generate_start_end_dates(2012)
        season.year = 2012
        season.start_date = start
        season.end_date = end
        season.save()
        self.assertSeasonSaved(season)

    def test_no_create_bad_season(self):
        # Make sure a season with a bad date isn't saved
        date = make_aware(datetime.datetime(2005, 02, 01), self.tz)
        with self.assertRaises(ValueError):
            season = Season.objects.get_current_season(date)

        # No date information at all
        season = Season()
        with self.assertRaises(ValueError):
            season.save()

        # Year too early
        season.year = 2005
        with self.assertRaises(ValueError):
            season.save()

        # Make a valid season object...
        start, end = Season.objects.generate_start_end_dates(2012)
        season = Season(year=2012, start_date=start, end_date=end)
        season.save()
        self.assertSeasonSaved(season)

        # ...then make sure modifying it to be invalid doesn't work
        season.year = 2005
        with self.assertRaises(ValueError):
            season.save()
        self.assertSeasonNotSaved(season)

    def test_season_does_not_already_exist_yearly_year(self):
        date = make_aware(datetime.datetime(2012, 02, 01), self.tz)
        season = Season.objects.get_current_season(date)
        start, end = Season.objects.generate_start_end_dates(date.year)
        self.assertSeasonEquals(season, 2012, start, end)

    def test_season_does_not_already_exist_mid_year(self):
        date = make_aware(datetime.datetime(2011, 06, 01), self.tz)
        season = Season.objects.get_current_season(date)
        start, end = Season.objects.generate_start_end_dates(date.year + 1)
        self.assertSeasonEquals(season, 2012, start, end)

    def test_season_does_not_already_exist_late_year(self):
        date = make_aware(datetime.datetime(2011, 11, 01), self.tz)
        season = Season.objects.get_current_season(date)
        start, end = Season.objects.generate_start_end_dates(date.year + 1)
        self.assertSeasonEquals(season, 2012, start, end)

    def test_get_current_existing_season(self):
        date = make_aware(datetime.datetime(2011, 11, 11), self.tz)
        season = Season.objects.get_current_season(date)
        start, end = Season.objects.generate_start_end_dates(date.year + 1)
        Season(year=date.year, start_date=start, end_date=end).save()
        self.assertSeasonEquals(season, 2012, start, end)
        self.assertFalse(season.is_current())

    def test_verbose_season_name(self):
        date = make_aware(datetime.datetime(2013, 11, 11), self.tz)
        season = Season.objects.get_current_season(date)
        self.assertEquals(season.verbose_name(), 'PiE Season 2014')

        date = make_aware(datetime.datetime(2012, 03, 02), self.tz)
        season = Season.objects.get_current_season(date)
        self.assertEquals(season.verbose_name(), 'PiE Season 2012')

    def test_season_number(self):
        start, end = Season.objects.generate_start_end_dates(2012)
        season = Season(year=2012, start_date=start, end_date=end)
        self.assertEquals(season.season_number, 4)

        start, end = Season.objects.generate_start_end_dates(2025)
        season = Season(year=2025, start_date=start, end_date=end)
        self.assertEquals(season.season_number, 17)

        start, end = Season.objects.generate_start_end_dates(2005)
        season = Season(year=2012, start_date=start, end_date=end)
        season.year = 2005
        with self.assertRaises(ValueError):
            _ = season.season_number

    def test_get_current(self):
        # Will first test with no arguments to check that it gets the current
        # season in that case, then test for with a date passed.

        # Since get_current depends on timezone.now(), we will use mox.
        # StubOut timezone.now() so that we can test get_current regardless
        # of the date constantly changing. By stubbing out it treats
        # 2012, 01, 01 as the date for today and puts everything relative to it
        self.mox.StubOutWithMock(timezone, 'now')

        # Since timezone.now() is used in two places for getting the current
        # season, we need to return the same object all the time.
        timezone.now().MultipleTimes().AndReturn(
            datetime.datetime(2012, 01, 01))

        self.mox.ReplayAll()
        season = Season.objects.get_current_season()
        self.assertTrue(season.is_current())
        self.mox.VerifyAll()

    def test_is_current(self):
        # Similar to the above test but tests is_current()
        self.mox.StubOutWithMock(timezone, 'now')
        timezone.now().MultipleTimes().AndReturn(
            datetime.datetime(2012, 01, 01))

        self.mox.ReplayAll()
        date = make_aware(datetime.datetime(2012, 01, 01), self.tz)
        season = Season.objects.get_current_season(date)
        start, end = Season.objects.generate_start_end_dates(2012)
        self.assertTrue(season.is_current())
        self.assertSeasonEquals(season, 2012, start, end)

        date = make_aware(datetime.datetime(2010, 9, 17), self.tz)
        season = Season.objects.get_current_season(date)
        start, end = Season.objects.generate_start_end_dates(2011)
        self.assertFalse(season.is_current())
        self.assertSeasonEquals(season, 2011, start, end)
        self.mox.VerifyAll()

    def test_get_current_season_with_date(self):
        date = make_aware(datetime.datetime(2025, 3, 17), self.tz)
        season = Season.objects.get_current_season(date)
        self.assertEquals(season.year, date.year)

        date = make_aware(datetime.datetime(2009, 3, 17), self.tz)
        season = Season.objects.get_current_season(date)
        self.assertEquals(season.year, date.year)
        start, end = Season.objects.generate_start_end_dates(date.year)
        Season(year=date.year, start_date=start, end_date=end).save()
        season = Season.objects.get_current_season(date)
        self.assertEquals(season.year, date.year)


class SchoolTest(TestCase):
    def test_uniqueness(self):
        school = School(name='Testing High School',
                        street_number=1234, street='Test St.', city='Berkeley',
                        state='California', zipcode=94704)
        school.save()
        duplicate_school = School(name='Testing High School',
                                  street_number=1234, street='Test St.',
                                  city='Berkeley', state='California',
                                  zipcode=94704)
        self.assertRaises(IntegrityError, duplicate_school.save)
