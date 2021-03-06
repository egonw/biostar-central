import datetime
from django.contrib.auth import logout
from django.contrib import messages
from main.server import models, const, notegen

class LastVisit(object):
    """
    Updates the last visit stamp at MINIMUM_TIME intervals
    """
    # minimum elapsed time
    MINIMUM_TIME = 60 * 1 # every 3 minutes

    def process_request(self, request):
        
        if request.user.is_authenticated():
            user = request.user
            profile = user.get_profile()
            
            if profile.suspended:
                logout(request)
                messages.error(request, 'Sorry, this account has been suspended. Please contact the administrators.')
                return None
            
            now = datetime.datetime.now()
            diff = (now - profile.last_visited).seconds
            
            # Prevent writing to the database too often
            if diff > self.MINIMUM_TIME:
                profile.last_visited = now
                profile.save()
            
                # award the beta tester badge
                models.apply_award(request=request, user=user, badge_name=const.BETA_TESTER_BADGE, messages=messages)
                    
        return None


class PermissionsMiddleware(object):
    ''' Calculates the logged-in user's permissions and adds it to the request object. '''
    def process_request(self, request):
        pass