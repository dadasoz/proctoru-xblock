"""
    ProctorU is an online proctoring company that allows a candidate to take their exam from home
"""
import datetime
import pkg_resources
import logging
import random
import pytz
import time
from tzlocal import get_localzone
import dateutil.parser

from django.contrib.auth.models import User
from django.template import Context, Template
from django.utils.translation import ugettext_lazy, ugettext as _

from xblock.core import XBlock
from xblock.fields import Scope, Integer, String, Boolean
from xblock.fragment import Fragment
from xblockutils.resources import ResourceLoader
from xblockutils2.studio_editable import StudioContainerXBlockMixin

from .api import ProctoruAPI

from .timezonemap import win_tz

# Please start and end the path with a trailing slash
log = logging.getLogger(__name__)
loader = ResourceLoader(__name__)


class AttrDict(dict):

    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class ProctorUXBlock(StudioContainerXBlockMixin, XBlock):

    """
    TO-DO: document what your XBlock does.
    """

    has_children = True

    display_name = String(display_name=ugettext_lazy("Exam Name"),
                          default="ProctorU XBlock",
                          scope=Scope.settings,
                          help=ugettext_lazy("This name appears in the horizontal navigation at the top of the page.")
                          )

    start_date = String(display_name=ugettext_lazy("Exam Start Date"),
                        default="2016-03-15T00:27:12.311587+00:00",
                        scope=Scope.settings,
                        help=ugettext_lazy("This will be the exam start date.")
                        )

    end_date = String(display_name=ugettext_lazy("Exam End Date"),
                      default="2016-03-20T00:27:12.311587+00:00",
                      scope=Scope.settings,
                      help=ugettext_lazy("This will be the exam end date.")
                      )

    duration = Integer(display_name=ugettext_lazy("Duration"),
                       default=30,
                       scope=Scope.settings,
                       help=ugettext_lazy("This will be exam duration.")
                       )

    exam_date = String(
        default=None,
        scope=Scope.user_state,
        help=ugettext_lazy("This will be the exam date.")
    )

    exam_time = String(
        default=None,
        scope=Scope.user_state,
        help=ugettext_lazy("This will be the exam time selected by student.")
    )

    password = String(
        default='password',
        scope=Scope.settings,
        help=ugettext_lazy("This will be the password for lock the exam.")
    )

    description = String(display_name=ugettext_lazy("Exam Description"),
                         default="ProctorU exam",
                         scope=Scope.settings,
                         help=ugettext_lazy("This will be Exam Description")
                         )

    notes = String(display_name=ugettext_lazy("Exam Notes"),
                   default="ProctorU Exam Notes",
                   scope=Scope.settings,
                   help=ugettext_lazy("This will be Exam Notes"))

    is_exam_scheduled = Boolean(help=ugettext_lazy("Is exam scheduled?"), default=False,
                                scope=Scope.user_state)

    exam_start_time = String(display_name=ugettext_lazy("Exam Start Time"),
                             default="2016-03-10T11:24:03.305494",
                             scope=Scope.settings,
                             help=ugettext_lazy("This will be exam start time"))

    exam_end_time = String(display_name=ugettext_lazy("Exam End Time"),
                           default="2016-03-10T11:24:03.305494",
                           scope=Scope.settings,
                           help=ugettext_lazy("This will be exam end time"))

    is_exam_completed = Boolean(help=ugettext_lazy("Is exam completed?"), default=False,
                                scope=Scope.user_state)

    is_started = Boolean(help=ugettext_lazy("Is exam completed?"), default=False,
                         scope=Scope.user_state)

    is_rescheduled = Boolean(help=ugettext_lazy("Is exam rescheduled?"), default=False,
                             scope=Scope.user_state)

    is_exam_start_clicked = Boolean(help=ugettext_lazy("Is exam start clicked?"), default=False,
                                    scope=Scope.user_state)

    is_exam_unlocked = Boolean(help=ugettext_lazy("Is exam unlocked?"), default=False,
                                    scope=Scope.user_state)

    is_exam_ended = Boolean(help=ugettext_lazy("Is exam ended?"), default=False,
                            scope=Scope.user_state)

    is_exam_canceled = Boolean(help="Is exam canceled?", default=False,
                               scope=Scope.user_state)

    time_zone = String(display_name=ugettext_lazy("Time Zone"),
                       default="Coordinated Universal Time",
                       scope=Scope.settings,
                       help=ugettext_lazy("Time zone of the instructor")
                       )

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def _is_studio(self):
        studio = False
        try:
            studio = self.runtime.is_author_mode
        except AttributeError:
            pass
        return studio

    def _user_is_staff(self):
        return getattr(self.runtime, 'user_is_staff', False)

    def get_course_key_string(self):
        return self.location.course_key._to_string()

    # TO-DO: change this view to display your data your own way.
    def student_view(self, context=None):
        """
        The primary view of the ProctorUXBlock, shown to students
        when viewing courses.
        """
        if self._is_studio():  # studio view
            fragment = Fragment(
                self._render_template('static/html/studio.html'))
            fragment.add_css(
                self.resource_string('static/css/proctoru.css'))
            return fragment
        if self._user_is_staff():
            return self.staff_view()
        else:  # student view
            api_obj = ProctoruAPI()
            fragment = Fragment()
            context = {}
            fragment.add_css(loader.load_unicode('static/css/proctoru.css'))
            fragment.add_css(
                loader.load_unicode('static/css/custom_bootstrap.css'))
            fragment.add_javascript(
                loader.load_unicode('static/js/src/proctoru.js'))
            if self.is_exam_ended:
                context.update({"self": self})
                fragment.add_content(
                    loader.render_template('static/html/exam_ended.html', context))
                fragment.initialize_js('ProctorUXBlockExamEnabled')
                return fragment
            if self.is_exam_unlocked:
                context.update({"self": self})
                fragment.add_content(
                    loader.render_template('static/html/exam_enabled.html', context))
                fragment.initialize_js('ProctorUXBlockExamEnabled')
                child_frags = self.runtime.render_children(
                    block=self, view_name='student_view')
                html = self._render_template(
                    'static/html/sequence.html', children=child_frags)
                fragment.add_content(html)
                fragment.add_frags_resources(child_frags)
                return fragment
            elif self.is_exam_start_clicked:
                context.update({"self": self})
                fragment.add_content(
                    loader.render_template('static/html/exam_password.html', context))
                fragment.initialize_js('ProctorUXBlockExamPassword')
                return fragment
            elif api_obj.is_user_created(self.runtime.user_id) and self.is_rescheduled:
                time_details = {
                    'exam_start_date_time': self.start_date,
                    'exam_end_date_time': self.end_date,
                }

                time_details = api_obj.get_time_details_api(
                    time_details, self.exam_date)

                if time_details.get('status') == "examdatepass":
                    context.update({'self': self, 'status': "examdatepass"})
                    fragment.add_content(
                        loader.render_template('static/html/error_template.html', context))
                else:
                    context = api_obj.render_shedule_ui(self.runtime.user_id, time_details, self.duration)
                    context.update({'self': self})

                    exam_time_heading = api_obj.get_formated_exam_start_date(self.exam_time, self.runtime.user_id)

                    context.update({
                        'exam_time_heading': exam_time_heading,
                    })

                    status = context.get('status')
                    if status == "error":
                        fragment.add_content(
                            loader.render_template('static/html/error_template.html', context))
                    elif status == "emptylist":
                        fragment.add_content(
                            loader.render_template('static/html/reshedule_form_proctoru.html', context))
                    else:
                        fragment.add_content(
                            loader.render_template('static/html/reshedule_form_proctoru.html', context))

                fragment.initialize_js('ProctorUXBlockSchedule')
                return fragment
            elif self.is_exam_scheduled:
                context.update({"exam":
                                api_obj.get_schedule_exam_arrived(self.runtime.user_id, self.get_course_key_string()), "self": self})
                fragment.add_content(
                    loader.render_template('static/html/exam_arrived_proctoru.html', context))
                fragment.initialize_js('ProctorUXBlockArrived')
                return fragment
            elif api_obj.is_user_created(self.runtime.user_id) and not self.is_exam_scheduled:
                time_details = {
                    'exam_start_date_time': self.start_date,
                    'exam_end_date_time': self.end_date,
                }

                time_details = api_obj.get_time_details_api(
                    time_details, self.exam_date)

                if time_details.get('status') == "examdatepass":
                    context.update({'self': self, 'status': "examdatepass"})
                    fragment.add_content(
                        loader.render_template('static/html/error_template.html', context))
                else:
                    context = api_obj.render_shedule_ui(self.runtime.user_id, time_details, self.duration)
                    context.update({'self': self})

                    status = context.get('status')
                    if status == "error":
                        fragment.add_content(
                            loader.render_template('static/html/error_template.html', context))
                    elif status == "emptylist":
                        fragment.add_content(
                            loader.render_template('static/html/shedule_form_proctoru.html', context))
                    else:
                        fragment.add_content(
                            loader.render_template('static/html/shedule_form_proctoru.html', context))

                fragment.initialize_js('ProctorUXBlockSchedule')
                return fragment
            else:
                fragment.add_content(
                    loader.render_template('static/html/proctoru.html', context))
                fragment.initialize_js('ProctorUXBlockCreate')
                return fragment

    def _render_template(self, ressource, **kwargs):
        template = Template(self.resource_string(ressource))
        context = dict({}, **kwargs)
        html = template.render(Context(context))
        return html

    def studio_view(self, context=None):
        """This is the view displaying xblock form in studio."""
        api_obj = ProctoruAPI()
        timezones = api_obj.get_time_zones()
        time_zone_list = timezones.get("data")

        fragment = Fragment()

        fragment.add_content(loader.render_template('static/html/studio_edit.html',
                                                    {'time_zone_list': time_zone_list,
                                                     'self': self}))
        fragment.add_css(
            self.resource_string('static/css/custom_bootstrap.css'))
        fragment.add_css(self.resource_string('static/css/proctoru.css'))
        fragment.add_javascript(
            self.resource_string("static/js/src/studio_edit.js"))
        fragment.initialize_js('ProctoruStudio')
        return fragment

    @XBlock.json_handler
    def studio_submit(self, data, suffix=''):
        """
        This function is used to add values to the xblock student view
        after user instaructor adds proctorU exam block.
        """

        start_date = data.get('exam_start_date')
        end_date = data.get('exam_end_date')

        start_time = data.get('exam_start_time')
        end_time = data.get('exam_end_time')

        exam_start_datetime = start_date+'/'+start_time
        exam_end_datetime = end_date + '/'+end_time

        tzobj = pytz.timezone(win_tz[data.get("time_zone")])

        start_datetime = datetime.datetime.strptime(
            exam_start_datetime, "%m/%d/%Y/%H:%M")

        start_datetime = start_datetime.replace(tzinfo=pytz.utc)

        start_datetime = start_datetime.astimezone(tzobj)

        # start_datetime = start_datetime.strftime('%Y-%m-%dT%H:%M:%S')

        start_datetime = start_datetime.isoformat()

        end_datetime = datetime.datetime.strptime(
            exam_end_datetime, "%m/%d/%Y/%H:%M")

        end_datetime = end_datetime.replace(tzinfo=pytz.utc)

        end_datetime = end_datetime.astimezone(tzobj)

        end_datetime = end_datetime.isoformat()

        # end_datetime = end_datetime.strftime('%Y-%m-%dT%H:%M:%S')

        self.display_name = data.get("exam_name", "")
        self.description = data.get("exam_description", "")
        self.duration = data.get("exam_duration", "")
        self.start_date = start_datetime
        self.end_date = end_datetime
        self.exam_start_time = data.get("exam_start_time", "")
        self.exam_end_time = data.get("exam_end_time", "")
        self.notes = data.get("exam_notes", "")
        self.password = data.get("exam_password", "")
        self.time_zone = data.get("time_zone")

        return {'status': 'success'}

    def author_edit_view(self, context):
        """We override this view from StudioContainerXBlockMixin to allow
        the addition of children blocks."""
        fragment = Fragment()
        self.render_children(context, fragment, can_reorder=True, can_add=True)
        return fragment

    def staff_view(self):
        """
        Primary view for instructor to Set exam using proctorU xBlock.
        """
        api_obj = ProctoruAPI()

        students = api_obj.get_student_sessions(
            self.get_course_key_string())

        fragment = Fragment()

        fragment.add_content(loader.render_template('static/html/staff-view.html',
                                                    {'self': self,
                                                     'students': students, }))
        fragment.add_css(
            self.resource_string('static/css/custom_bootstrap.css'))
        fragment.add_css(self.resource_string('static/css/proctoru.css'))
        fragment.add_javascript(
            self.resource_string("static/js/src/lms_view.js"))
        fragment.initialize_js('ProctoruStaffBlock')
        return fragment

    @XBlock.json_handler
    def get_time_zones(self, data=None, suffix=None):
        """
        Get time zones by calling getTimeZoneList of ProctorU.
        """
        api_obj = ProctoruAPI()
        return api_obj.get_time_zones()

    @XBlock.json_handler
    def create_proctoru_account(self, data=None, suffix=None):
        """
        Create ProcorU account
        """
        api_obj = ProctoruAPI()
        return api_obj.create_user(self.runtime.user_id, data)

    @XBlock.json_handler
    def shedule_page_handler(self, data=None, suffix=None):
        """
        Return html for shedule page
        """
        api_obj = ProctoruAPI()
        context = api_obj.render_shedule_ui(self.runtime.user_id)

        # context.update({'calendar_arrow_url': self.runtime.local_resource_url(self, 'public/images/arrow.jpg')})

        html = loader.render_template(
            'static/html/shedule_form_proctoru.html', context)
        return {
            'html': html,
        }

    @XBlock.json_handler
    def get_available_schedule(self, data=None, suffix=None):
        """
        Get available schedule
        """
        self.exam_date = data.get('date')
        return {
            'status': _('success')
        }

    @XBlock.json_handler
    def reschedule_exam(self, data=None, suffix=None):
        """
        Get available schedule
        """
        self.is_rescheduled = True
        return {
            'status': _('success')
        }

    @XBlock.json_handler
    def start_exam(self, data=None, suffix=None):
        """
        Get available schedule
        """
        self.is_exam_start_clicked = True
        return {
            'status': _('success')
        }

    @XBlock.json_handler
    def cancel_exam(self, data=None, suffix=None):
        """
        Get available schedule
        """
        api_obj = ProctoruAPI()
        response_data = api_obj.cancel_exam(
            User.objects.get(pk=self.runtime.user_id), self.get_course_key_string())
        self.is_exam_canceled = True
        self.is_exam_scheduled = False
        if response_data.get('response_code') == 1:
            return {
                'status': 'success',
                'msg': 'Successfully canceled!',
            }
        else:
            return {
                'status': 'error',
                'msg': "Already canceled!",
            }

    @XBlock.json_handler
    def unlock_exam(self, data=None, suffix=None):
        """
        Get available schedule
        """
        password = data.get('password')
        if password == self.password:
            self.is_exam_unlocked = True
            api_obj = ProctoruAPI()
            exam_status = api_obj.start_exam(
                User.objects.get(pk=self.runtime.user_id), self.get_course_key_string())
            if exam_status:
                return {
                    'status': _('success')
                }
            else:
                return {
                    'status': _('error'),
                    'msg': _('Database error'),
                }
        else:
            return {
                'status': _('error'),
                'msg': _("invalid password")
            }

    @XBlock.json_handler
    def end_exam(self, data=None, suffix=None):
        """
        Get available schedule
        """
        self.is_exam_unlocked = False
        self.is_exam_ended = True
        api_obj = ProctoruAPI()
        exam_status = api_obj.end_exam(
            User.objects.get(pk=self.runtime.user_id), self.get_course_key_string())
        if exam_status:
            return {
                'status': _('success')
            }
        else:
            return {
                'status': _('error'),
                'msg': _('Database error'),
            }

    @XBlock.json_handler
    def call_addhoc(self, data=None, suffix=None):
        """
        call adhoc process
        """
        # TO DO
        # Create and store student_id and reservation_id as per api data type and store in db
        # Provide required input to adadhocprocess.
        # Country needs to be 2 digit, rightnow static
        api_obj = ProctoruAPI()

        user_data = api_obj.get_user(self.runtime.user_id)

        reservation_id = ''.join(
            random.choice('0123456789ABCDEF') for i in range(40))

        shedule_time = data.get('shedule_time', None)

        student_data = {
            'time_sent': datetime.datetime.utcnow().isoformat(),
            'student_id': user_data.get('id', None),
            'last_name': user_data.get('last_name', None),
            'first_name': user_data.get('first_name', None),
            'email': user_data.get('email', None),
            'address1': user_data.get('address', None),
            'city': user_data.get('city', None),
            'country': user_data.get('country', "US"),
            'phone1': user_data.get('phone_number', None),
            'time_zone_id': user_data.get('time_zone', None),
            'description': 'test description11',
            'duration': self.duration,
            'start_date': shedule_time,
            'takeitnow': 'Y',
            'reservation_id': reservation_id,
        }

        if self.is_rescheduled:
            exam = api_obj.get_schedule_exam_arrived(
                self.runtime.user_id, self.get_course_key_string())
            if exam:
                student_data['reservation_id'] = exam.reservation_id
                student_data['reservation_no'] = exam.reservation_no

        json_response = api_obj.add_adhoc_process(student_data)
        if json_response.get('response_code') == 1:
            exam_data = {
                "start_date": shedule_time,
                "reservation_id": reservation_id,
                "reservation_no": json_response.get('data').get('reservation_no'),
                "user": User.objects.get(pk=int(user_data.get('id', None))),
                "course_id": self.get_course_key_string(),
                "url": json_response.get('data').get('url'),
            }
            # TODO when actule schedule done
            self.exam_time = shedule_time
            self.is_exam_scheduled = True
            self.is_rescheduled = False
            self.is_exam_canceled = False

            api_obj.set_exam_schedule_arrived(exam_data)

            return {
                'status': _('success')
            }
        elif json_response.get('response_code') == 2:
            return {
                'status': _('error'),
                'msg': _('exam already scheduled')
            }
        else:
            return {
                'status': _('error'),
                'msg': _('Please contact administrator')
            }

    @XBlock.json_handler
    def cancle_rescheduling(self,data=None,suffix=""):
        """
        Cancel Rescheduling.
        """
        self.is_rescheduled = False
        return {"message": _('success')}

    @staticmethod
    def is_exam_available(self):
        try:
            utcmoment_unaware = datetime.datetime.utcnow()
            utcmoment = utcmoment_unaware.replace(tzinfo=pytz.utc)
            d1_ts = time.mktime(self.timetuple())
            d2_ts = time.mktime(utcmoment.timetuple())
            rem_minutes = int(d1_ts-d2_ts) / 60
            if rem_minutes >= 2:
                return True
            else:
                return False
        except:
            return False

    # TO-DO: change this to create the scenarios you'd like to see in the
    # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("ProctorUXBlock",
             """<proctoru/>
             """),
            ("Multiple ProctorUXBlock",
             """<vertical_demo>
                <proctoru/>
                <proctoru/>
                <proctoru/>
                </vertical_demo>
             """),
        ]
