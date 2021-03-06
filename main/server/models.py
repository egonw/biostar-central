"""
Model definitions.

Note: some models are denormalized by design, this greatly simplifies (and speeds up) 
the queries necessary to fetch a certain entry.

"""
import os, random, hashlib, string

from django.db import models
from django.db import transaction
from django.contrib.auth.models import User, Group
from django.contrib import admin
from django.conf import settings

from mptt.models import MPTTModel, TreeForeignKey
from datetime import datetime, timedelta
from main.server import html, notegen

# import all constants
from main.server.const import *

import markdown

class UserProfile( models.Model ):
    """
    Stores user options

    >>> user, flag = User.objects.get_or_create(first_name='Jane', last_name='Doe', username='jane', email='jane')
    >>> prof = user.get_profile()
    >>> prof.json = dict( message='Hello world' )
    >>> prof.save()
    """
    user  = models.OneToOneField(User, unique=True, related_name='profile')
    
    # this designates a user as moderator
    type  = models.IntegerField(choices=USER_TYPES, default=USER_NORMAL)
    
    # globally unique id
    uuid = models.TextField(null=False,  db_index=True, unique=True)

    score = models.IntegerField(default=0, blank=True)
    reputation = models.IntegerField(default=0, blank=True, db_index=True)
    views = models.IntegerField(default=0, blank=True)
    bronze_badges = models.IntegerField(default=0)
    silver_badges = models.IntegerField(default=0)
    gold_badges   = models.IntegerField(default=0)
    json  = models.TextField(default="", null=True)
    last_visited = models.DateTimeField(auto_now=True)
    suspended    = models.BooleanField(default=False, null=False)
    
    about_me = models.TextField(default="(about me)", null=True)
    html     = models.TextField(default="", null=True)
    location = models.TextField(default="", null=True)
    website  = models.URLField(default="", null=True, max_length=100)
    openid   = models.URLField(default="http://www.biostars.org", null=True)
    display_name  = models.CharField(max_length=35, default='User', null=False,  db_index=True)
    last_login_ip = models.IPAddressField(default="0.0.0.0", null=True)
    openid_merge  = models.NullBooleanField(default=False, null=True)
      
    @property
    def is_moderator(self):
        return (self.type == USER_MODERATOR) or (self.type == USER_ADMIN)
    
    @property
    def is_admin(self):
        return self.type == USER_ADMIN
    
    @property
    def is_active(self):
        if self.suspended:
            return False
        if self.is_moderator or self.score >= settings.MINIMUM_REPUTATION:
            return True
        
        # right not we let it fall through to True
        # needs more throttles may go here here
        return True
    
    def get_absolute_url(self):
        return "/user/show/%i/" % self.user.id


    def status(self):
        if self.suspended:
            return 'suspended'
        else:
            return 'active'

    def authorize(self, moderator):
        "Authorizes access to a user data moderator"
        
        # we will cascade through options here

        # no access to anonymous users
        if  moderator.is_anonymous():
            return False

        # other admins may only be changed via direct database access
        if self.is_admin:
            return False
        
        # moderator that is also an admin may access everyone else
        if moderator.profile.is_admin:
            return True

        # a moderator's private info may not be accessed past this point
        if self.is_moderator:
            return False

        return moderator.profile.is_moderator
    
    def editable(self, moderator):
        "Is this users content editable by a moderator"
       
        # everyone can access themselves
        if self.user == moderator:
            return True
        
        return self.authorize(moderator)


    @property
    def note_count(self):
        note_count = Note.objects.filter(target=self.user).count()
        new_count  = Note.objects.filter(target=self.user, unread=True).count()
        return (note_count, new_count)
    
 
class Tag(models.Model):
    name = models.TextField(max_length=50)
    count = models.IntegerField(default=0)
    
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'count')

admin.site.register(Tag, TagAdmin)

class PostManager(models.Manager):
    ''' Used for all posts (question, answer, comment); returns only non-deleted posts '''
    def get_query_set(self):
        return super(PostManager, self).get_query_set().select_related('author','author__profile','children',).filter(post_type=POST_COMMENT)

class AnswerManager(models.Manager):
    ''' Used for all posts (question, answer, comment); returns only non-deleted posts '''
    def get_query_set(self):
        return super(AnswerManager, self).get_query_set().select_related('author','author__profile','children').filter(post_type=POST_ANSWER)

class Post(MPTTModel):
    """
    A posting is the basic content generated by a user
    
    >>> user, flag = User.objects.get_or_create(first_name='Jane', last_name='Doe', username='jane', email='jane')
    >>> post = Post.objects.create(author=user, post_type=POST_QUESTION)
    >>> content ='*A*'
    >>> post.create_revision(content=content)
    >>> post.html
    u'<p><em>A</em></p>'
    """
    author = models.ForeignKey(User)
    content = models.TextField(blank=True) # The underlying Markdown
    html    = models.TextField(blank=True) # this is the sanitized HTML for display
    title   = models.TextField(blank=True)
    slug    = models.SlugField(blank=True, max_length=200)
    tag_string = models.CharField(max_length=200) # The tag string is the canonical form of the post's tags
    tag_set = models.ManyToManyField(Tag) # The tag set is built from the tag string and used only for fast filtering
    views = models.IntegerField(default=0, blank=True)
    score = models.IntegerField(default=0, blank=True)

    creation_date = models.DateTimeField(db_index=True)
    lastedit_date = models.DateTimeField()
    lastedit_user = models.ForeignKey(User, related_name='editor')
    deleted = models.BooleanField()
    closed  = models.BooleanField()
    
    post_type = models.IntegerField(choices=POST_TYPES, db_index=True)
    
    # this will maintain parent-child replationships between poss
    #parent = models.ForeignKey('self', related_name="children", null=True, blank=True)
    
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children')
    
    #
    # denormalized fields only that only apply to specific cases
    #
    comment_count  = models.IntegerField(default=0)
    revision_count = models.IntegerField(default=0)
    child_count = models.IntegerField(default=0, blank=True) # number of children (other posts associated with the post)
    post_accepted = models.BooleanField(default=False) # the post has been accepted
    answer_accepted = models.BooleanField() # if this was 
    unanswered = models.BooleanField(db_index=True) # this is a question with no answers
    answer_count = models.IntegerField(default=0, blank=True)
   
    # this field will be used to allow posts to float back into relevance
    touch_date = models.DateTimeField(db_index=True) 
    
    class MPTTMeta:
        order_insertion_by = ['creation_date']
    
    def get_absolute_url(self):
        return "/post/show/%i/" % self.id

    @property
    def status(self):
        # some say this is ugly but simplifies greatly the templates
        if self.post_accepted:
            return 'answer-accepted'
        elif self.answer_count:
            return 'answered'
        else:
            return 'unanswered'

    @property    
    def post_type_name(self):
        "Returns a user friendly name for the post type"
        return POST_REV_MAP[self.post_type]
      
    @property
    def is_owner(self, user):
        return (self.author == user)
    
    @transaction.commit_on_success
    def notify(self):
        "Generates notifications to all users related with this post. Invoked only on the creation of the post"
        # create a notification for the post that includes all authors of every child
        root = self.get_root()

        authors = set( [ root.author] )
        for child in root.get_descendants():
            authors.add( child.author )
        text = notegen.post_action(user=self.author, post=self)
       
        # the current author will get a message that is not new
        authors.remove(self.author)
       
        for target in authors:
            Note.send(sender=self.author, target=target, content=text, type=NOTE_USER, unread=True, date=self.creation_date)

        # for the current post author  this is not a new message
        Note.send(sender=self.author, target=self.author, content=text, type=NOTE_USER, unread=False, date=self.creation_date)

    def changed(self, content=None, title=None, tag_string=None):
        "Tests post parameters"
        return (content == self.content and tag_string == self.tag_string and title == self.title)
            
    def create_revision(self, content=None, title=None, tag_string=None, author=None, date=None, action=REV_NONE):
        """
        Creates a new revision of the post with the given data.
        Content, title and tags are assumed to be unmodified if not given.
        Author is assumed to be same as original author if not given.
        Date is assumed to be now if not given.
        """
        content = content or self.content
        title = title or self.title
        tag_string = tag_string or self.tag_string
        author = author or self.author
        date = date or datetime.now()
        
        # transform the content to UNIX style line endings
        content = content.replace('\r\n', '\n')
        content = content.replace('\r', '\n')
        
        # creates a new revision for the post
        revision = PostRevision(post=self, content=content, tag_string=tag_string, title=title, author=author, date=date, action=action)
        revision.save()
        
        # Update our metadata
        self.lastedit_user = author
        self.content = content
        self.title = title
        self.set_tags(tag_string)
        self.save()

    def get_title(self):
        title = self.title
        if self.deleted:
            title = "%s [deleted ]" % self.title
        elif self.closed:
            title = "%s [closed]" % self.title
        return title
            
    def current_revision(self):
        """
        Returns the most recent revision of the post. Primarily useful for getting the
        current raw text of the post
        """
        return self.revisions.order_by('date')[0]
        
    def moderator_action(self, action, moderator, date=None):
        """
        Performs a moderator action on the post. Takes an action (one of REV_ACTIONS)
        and a user. Date is assumed to be now if not provided
        """
        
        text = notegen.post_moderator_action(user=moderator, post=self, action=action)
        Note.send(target=self.author, sender=moderator, post=self, content=text,  type=NOTE_MODERATOR)
        
        self.create_revision(action=action)

        if action == REV_CLOSE:
            self.closed = True
        elif action == REV_REOPEN:
            self.closed = False
        elif action == REV_DELETE:
            self.deleted = True
        elif action == REV_UNDELETE:
            self.deleted = False
        else:
            raise Exception('Invalid moderator action %s' % action)
        
        self.save()

    def authorize(self, user, strict=True):
        "Verfifies access by a request object. Strict mode fails immediately."

        # no access to anonymous users
        if user.is_anonymous():
            return False
        
        # everyone may access posts they have authored
        if user == self.author:
            return True

        return user.profile.is_moderator

    def get_vote(self, user, vote_type):
        if user.is_anonymous():
            return None
        try:
            return self.votes.get(author=user, type=vote_type)
        except Vote.DoesNotExist:
            return None
        
    def add_vote(self, user, vote_type):
        vote = Vote(author=user, type=vote_type, post=self)
        vote.save()
        return vote
        
    def remove_vote(self, user, vote_type):
        ''' Removes a vote from a user of a certain type if it exists
        Returns True if removed, False if it didn't exist'''
        vote = self.get_vote(user, vote_type)
        if vote:
            vote.delete()
            return True
        return False
        
    def set_tags(self, tag_string):
        ''' Sets the post's tags to a space-separated string of tags '''
        self.tag_string = tag_string
        self.save()
        self.tag_set.clear()
        if not tag_string:
            return
        tags = []
        for tag_name in tag_string.split(' '):
            try:
                tags.append(Tag.objects.get(name=tag_name))
            except Tag.DoesNotExist:
                tag = Tag(name=tag_name)
                tag.save()
                tags.append(tag)
        self.tag_set.add(*tags)
        
    def get_tags(self):
        ''' Returns the post's tags as a list of strings '''
        return self.tag_string.split(' ')
    
    def details(self):
        return
    
    def apply(self, dir):
        is_answer  = self.parent and self.post_type == POST_ANSWER
        is_comment = self.parent and self.post_type == POST_COMMENT
        if is_answer:
            self.parent.answer_count += dir
            self.parent.save()
        if is_comment:
            self.parent.comment_count += dir
            self.parent.save()
    
    def comments(self):
        objs = Post.objects.filter(parent=self, post_type=POST_COMMENT).select_related('author','author__profile')
        return objs
    
    def css(self):
        "Used during rendering"
        if self.deleted:
            return "post-deleted"
        elif self.closed:
            return "post-closed"
        else:
            return "post-active"
        
    objects  = models.Manager()    
    answers  = AnswerManager()

class PostRevision(models.Model):
    """
    Represents various revisions of a single post
    """
    post    = models.ForeignKey(Post, related_name='revisions')
    
    content = models.TextField()
    tag_string = models.CharField(max_length=200)
    title = models.TextField(blank=True)
    
    # Moderator action performed in this revision, if applicable
    action = models.IntegerField(choices=REV_ACTIONS, default=REV_NONE)
    
    author = models.ForeignKey(User)
    date   = models.DateTimeField()
    
    def html(self):
        '''We won't cache the HTML in the DB because revisions are viewed fairly infrequently '''
        return html.generate(self.content)
        
    def get_tags(self):
        ''' Returns the revision's tags as a list of strings '''
        return self.tag_string.split(' ')
    
    def apply(self, dir=1):
        self.post.revision_count += dir
        self.post.save()
 
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', )

admin.site.register(Post, PostAdmin)

class PostRevisionAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', )

admin.site.register(PostRevision, PostRevisionAdmin)

class Note(models.Model):
    """
    Creates simple notifications that are active until the user deletes them
    """
    sender  = models.ForeignKey(User, related_name="note_sender") # the creator of the notification
    target  = models.ForeignKey(User, related_name="note_target", db_index=True) # the user that will get the note
    post    = models.ForeignKey(Post, related_name="note_post",null=True, blank=True) # the user that will get the note
    content = models.CharField(max_length=5000, default='') # this contains the raw message
    html    = models.CharField(max_length=5000, default='') # this contains the santizied content
    date    = models.DateTimeField(null=False)
    unread  = models.BooleanField(default=True)
    type    = models.IntegerField(choices=NOTE_TYPES, default=NOTE_USER)

    @classmethod
    def send(self, **params):
        note = Note.objects.create(**params)
        return note
        
    def get_absolute_url(self):
        return "/user/show/%s/" % self.target.id         

    @property
    def status(self):
        return 'new' if self.unread else 'old'



class Vote(models.Model):
    """
    >>> user, flag = User.objects.get_or_create(first_name='Jane', last_name='Doe', username='jane', email='jane')
    >>> post = Post.objects.create(author=user, post_type=POST_QUESTION)
    >>> post.create_revision(content='ABC')
    >>> vote = Vote(author=user, post=post, type=VOTE_UP)
    >>> vote.score()
    1
    """
    author = models.ForeignKey(User)
    post = models.ForeignKey(Post, related_name='votes')
    type = models.IntegerField(choices=VOTE_TYPES)
    
    def score(self):
        return POST_SCORE.get(self.type, 0)
    
    def reputation(self):
        return USER_REP.get(self.type, 0)
        
    def voter_reputation(self):
        return VOTER_REP.get(self.type, 0)
    
    def apply(self, dir=1):
        "Applies the score and reputation changes. Direction can be set to -1 to undo (ie delete vote)"
        if self.reputation():
            prof = self.post.author.get_profile()
            prof.score += dir * self.reputation()
            prof.save()
        
        if self.voter_reputation():
            prof = self.author.get_profile()
            prof.score += dir * self.voter_reputation()
            prof.save()

        if self.score():
            self.post.score += dir * self.score()
            self.post.save()
            
        if self.type == VOTE_ACCEPT:
            answer   = self.post
            question = self.post.parent
            if dir == 1:
                answer.post_accepted = True
                question.answer_accepted = True
            else:
                answer.post_accepted = False
                question.answer_accepted = False
            answer.save()
            #question.save()
            
           
class Badge(models.Model):
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    type = models.IntegerField(choices=BADGE_TYPES)
    unique = models.BooleanField(default=False) # Unique badges may be earned only once
    secret = models.BooleanField(default=False) # Secret badges are not listed on the badge list
    count  = models.IntegerField(default=0) # Total number of times awarded
    
    def get_absolute_url(self):
        return "/badge/show/%s/" % self.id

class Award(models.Model):
    '''
    A badge being awarded to a user.Cannot be ManyToManyField
    because some may be earned multiple times
    '''
    badge = models.ForeignKey(Badge)
    user = models.ForeignKey(User)
    date = models.DateTimeField()
    
    def apply(self, dir=1):
        type = self.badge.type
        prof = self.user.get_profile()
        if type == BADGE_BRONZE:
            prof.bronze_badges += dir
        if type == BADGE_SILVER:
            prof.silver_badges += dir
        if type == BADGE_GOLD:
            prof.gold_badges += dir
        prof.save()
        self.badge.count += dir
        self.badge.save()
    
  
def apply_award(request, user, badge_name, messages=None):

    badge = Badge.objects.get(name=badge_name)
    award = Award.objects.filter(badge=badge, user=user)
    
    if award and badge.unique:
        # this badge has already been awarded
        return

    community = User.objects.get(username='community')
    award = Award.objects.create(badge=badge, user=user)
    text = notegen.badgenote(award.badge)
    note = Note.send(sender=community, target=user, content=text)
    if messages:
        messages.info(request, note.html)

# most of the site functionality, reputation change
# and voting is auto applied via database signals
#
# data migration will need to route through
# these models (this application) to ensure that all actions
# get applied properly
#
from django.db.models import signals

# Many models have apply() methods that need to be called when they are created
# and called with dir=-1 when deleted to update something.
MODELS_WITH_APPLY = [ Post, Vote, Award, PostRevision ]
    
def apply_instance(sender, instance, created, raw, *args, **kwargs):
    "Applies changes from an instance with an apply() method"
    if created and not raw: # Raw is true when importing from fixtures, in which case votes are already applied
        instance.apply(+1)

def unapply_instance(sender, instance,  *args, **kwargs):
    "Unapplies an instance when it is deleted"
    instance.apply(-1)
    
for model in MODELS_WITH_APPLY:
    signals.post_save.connect(apply_instance, sender=model)
    signals.post_delete.connect(unapply_instance, sender=model)

def make_uuid():
    "Returns a unique id"
    x = random.getrandbits(256)
    u = hashlib.md5(str(x)).hexdigest()
    return u

def create_profile(sender, instance, created, *args, **kwargs):
    "Post save hook for creating user profiles on user save"
    if created:
        uuid = make_uuid() 
        display_name = html.nuke(instance.get_full_name())
        UserProfile.objects.create(user=instance, uuid=uuid, display_name=display_name)

def update_profile(sender, instance, *args, **kwargs):
    "Pre save hook for profiles"
    instance.html = html.generate(instance.about_me)
    
from django.template.defaultfilters import slugify

def create_post(sender, instance, *args, **kwargs):
    "Pre save post information that needs to be applied"
    
    if not hasattr(instance, 'lastedit_user'):
        instance.lastedit_user = instance.author
    
    if not instance.creation_date:
        instance.creation_date = datetime.now()
    
    if not instance.lastedit_date:
        instance.lastedit_date = datetime.now()
    
    if not instance.title:
        instance.title = "%s: %s" %(POST_MAP[instance.post_type], instance.get_root().title)

    instance.slug = slugify(instance.title)
        
    # generate the HTML from the content    
    instance.html = html.generate(instance.content)
    
    # set the touch date
    instance.touch_date = datetime.now()

def create_post_note(sender, instance, created, *args, **kwargs):
    "Post save notice on a post"
    if created:
        # when a new post is created all descendants are notified
        instance.notify()

def create_award(sender, instance, *args, **kwargs):
    "Pre save award function"
    if not instance.date:
        instance.date = datetime.now()

def create_note(sender, instance, *args, **kwargs):
    "Pre save notice function"
    if not instance.date:
        instance.date = datetime.now()
    instance.html = html.generate(instance.content)
  
def tags_changed(sender, instance, action, pk_set, *args, **kwargs):
    "Applies tag count updates upon post changes"
    if action == 'post_add':
        for pk in pk_set:
            tag = Tag.objects.get(pk=pk)
            tag.count += 1
            tag.save()
    if action == 'post_delete':
        for pk in pk_set:
            tag = Tag.objects.get(pk=pk)
            tag.count -= 1
            tag.save()
    if action == 'pre_clear': # Must be pre so we know what was cleared
        for tag in instance.tag_set.all():
            tag.count -= 1
            tag.save()
            
def tag_created(sender, instance, created, *args, **kwargs):
    "Zero out the count of a newly created Tag instance to avoid double counting in import"
    if created and instance.count != 0:
        # To avoid infinite recursion, we must disconnect the signal temporarily
        signals.post_save.disconnect(tag_created, sender=Tag)
        instance.count = 0
        instance.save()
        signals.post_save.connect(tag_created, sender=Tag)

# now connect all the signals
signals.post_save.connect( create_profile, sender=User )
signals.pre_save.connect( update_profile, sender=UserProfile )

signals.pre_save.connect( create_post, sender=Post )
signals.post_save.connect( create_post_note, sender=Post )

signals.pre_save.connect( create_note, sender=Note )
signals.pre_save.connect( create_award, sender=Award )
signals.m2m_changed.connect( tags_changed, sender=Post.tag_set.through )
signals.post_save.connect( tag_created, sender=Tag )

# adding full text search capabilities

from whoosh import store, fields, index

WhooshSchema = fields.Schema(content=fields.TEXT(), pid=fields.NUMERIC(stored=True))

def create_index(sender=None, **kwargs):
    if not os.path.exists(settings.WHOOSH_INDEX):
        os.mkdir(settings.WHOOSH_INDEX)
        ix = index.create_in(settings.WHOOSH_INDEX, WhooshSchema)
        writer = ix.writer()

signals.post_syncdb.connect(create_index)

def update_index(sender, instance, created, **kwargs):
    
    ix = index.open_dir(settings.WHOOSH_INDEX)
    writer = ix.writer()

    if instance.post_type in POST_FULL_FORM:
        text = instance.title + instance.content  
    else:
        text = instance.content

    if created:                     
        writer.add_document(content=text, pid=instance.id)
        writer.commit()
    else:
        writer.update_document(content=text, pid=instance.id)        
        writer.commit()

def set_text_indexing(switch):
    if switch:
        signals.post_save.connect(update_index, sender=Post)
    else:
        signals.post_save.disconnect(update_index, sender=Post)

set_text_indexing(True)