from chosen import forms as chosen_forms
from django import forms
from django.utils.safestring import mark_safe

from quark.base.forms import ChosenTermMixin
from quark.courses.models import CourseInstance
from quark.courses.models import Department
from quark.courses.models import Instructor
from quark.exams.models import Exam
from quark.exams.models import ExamFlag
from quark.exams.models import InstructorPermission
from quark.shortcuts import get_file_mimetype


class ExamForm(ChosenTermMixin, forms.ModelForm):
    """Used as a base for UploadForm and EditForm."""
    department = chosen_forms.ChosenModelChoiceField(
        queryset=Department.objects.all())
    course_number = forms.CharField()
    instructors = chosen_forms.ChosenModelMultipleChoiceField(
        queryset=Instructor.objects.all())

    course_instance = None  # set by check_course_instance

    class Meta(object):
        model = Exam
        fields = ('exam_number', 'exam_type')

    def __init__(self, *args, **kwargs):
        super(ExamForm, self).__init__(*args, **kwargs)
        self.fields['exam_type'].label = 'Exam or solution file?'
        self.fields.keyOrder = [
            'department', 'course_number', 'instructors', 'term', 'exam_number',
            'exam_type']

    def check_course_instance(self, cleaned_data):
        """Check if the course instance exists."""
        course_instance = CourseInstance.objects.filter(
            course__department=self.cleaned_data.get('department'),
            course__number=self.cleaned_data.get('course_number'),
            term=self.cleaned_data.get('term'))
        # check instructors to prevent trying to iterate over nothing
        if self.cleaned_data.get('instructors') is None:
            raise forms.ValidationError('Please fill out all fields.')
        for instructor in self.cleaned_data.get('instructors'):
            course_instance = course_instance.filter(instructors=instructor)
        if len(course_instance) == 0:
            instructors = ', '.join(
                [i.last_name for i in self.cleaned_data.get('instructors')])
            raise forms.ValidationError(
                '{department} {number} ({term}), taught by {instructors}'
                ' never existed.'.format(
                    term=self.cleaned_data.get('term').verbose_name(),
                    department=self.cleaned_data.get('department'),
                    number=self.cleaned_data.get('course_number'),
                    instructors=instructors))
        self.course_instance = course_instance[0]

    def save(self, *args, **kwargs):
        """Add a course instance to the exam."""
        self.instance.course_instance = self.course_instance
        return super(ExamForm, self).save(*args, **kwargs)


class UploadForm(ExamForm):
    exam_file = forms.FileField(
        label='File (PDF only please)')
    agreed = forms.BooleanField(required=True, label=mark_safe(
        'I agree, per campus policy on Course Note-Taking and Materials '
        '(available <a href="http://campuspol.chance.berkeley.edu/policies/'
        'coursenotes.pdf">here</a>), that I am allowed to upload '
        'this document.'))

    class Meta(ExamForm.Meta):
        fields = ExamForm.Meta.fields + ('exam_file',)

    def __init__(self, *args, **kwargs):
        super(UploadForm, self).__init__(*args, **kwargs)
        self.fields.keyOrder += ['exam_file', 'agreed']

    def clean_exam_file(self):
        """Check if uploaded exam file is of an acceptable format."""
        exam_file = self.cleaned_data.get('exam_file')
        # Check if a file was actually uploaded
        if not exam_file:
            raise forms.ValidationError('Please attach a file.')

        if get_file_mimetype(exam_file) != 'application/pdf':
            raise forms.ValidationError('Uploaded file must be a PDF file.')
        return exam_file

    def clean(self):
        """Check if uploaded exam already exists."""
        cleaned_data = super(UploadForm, self).clean()
        self.check_course_instance(cleaned_data)
        duplicates = Exam.objects.filter(
            course_instance=self.course_instance,
            exam_number=cleaned_data.get('exam_number'),
            exam_type=cleaned_data.get('exam_type'))
        if duplicates.exists():
            raise forms.ValidationError(
                'This exam already exists in the database.')

    def save(self, *args, **kwargs):
        """Check if professors are blacklisted."""
        for instructor in self.cleaned_data.get('instructors'):
            permission = InstructorPermission.objects.get_or_create(
                instructor=instructor)[0].permission_allowed
            if permission is False:
                self.instance.blacklisted = True
        return super(UploadForm, self).save(*args, **kwargs)


class EditForm(ExamForm):
    class Meta(ExamForm.Meta):
        fields = ExamForm.Meta.fields + ('verified',)

    def __init__(self, *args, **kwargs):
        super(EditForm, self).__init__(*args, **kwargs)
        self.fields['department'].initial = (
            self.instance.course_instance.course.department)
        self.fields['course_number'].initial = (
            self.instance.course_instance.course.number)
        self.fields['instructors'].initial = (
            self.instance.course_instance.instructors.all())
        self.fields['term'].initial = self.instance.course_instance.term
        self.fields.keyOrder += ['verified']

    def clean(self):
        """Check if an exam already exists with the new changes, excluding the
        current exam being edited.
        """
        cleaned_data = super(EditForm, self).clean()
        self.check_course_instance(cleaned_data)
        duplicates = Exam.objects.filter(
            course_instance=self.course_instance,
            exam_number=cleaned_data.get('exam_number'),
            exam_type=cleaned_data.get('exam_type')).exclude(
            pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(
                'This exam already exists in the database. '
                'Please double check and delete as necessary.')
        return cleaned_data


class FlagForm(forms.ModelForm):
    class Meta(object):
        model = ExamFlag
        fields = ('reason',)


class FlagResolveForm(forms.ModelForm):
    class Meta(object):
        model = ExamFlag
        fields = ('resolution',)


class EditPermissionForm(forms.ModelForm):
    permission_allowed = forms.NullBooleanField()

    class Meta(object):
        model = InstructorPermission
        fields = ('permission_allowed', 'correspondence')


class BaseEditPermissionFormset(forms.formsets.BaseFormSet):
    def total_form_count(self):
        """Sets the number of forms equal to the number of instructor
        permissions.
        """
        return InstructorPermission.objects.all().count()


# pylint: disable=C0103
EditPermissionFormSet = forms.formsets.formset_factory(
    EditPermissionForm, formset=BaseEditPermissionFormset)
