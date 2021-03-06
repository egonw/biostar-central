from django import forms
from main.server import const
import string

P_TITLE, P_CONTENT, P_TAG = 'Post title', 'Post content', 'tag1'
class PostForm(forms.Form):
    """
    A form representing a new question
    """
    title      = forms.CharField(max_length=250,  initial=P_TITLE)
    content    = forms.CharField(max_length=5000, initial=P_CONTENT)
    tag_string = forms.CharField(max_length=250,  initial=P_TAG, widget=forms.TextInput(attrs={'style':'width:700px;'}))
    post_type  = forms.ChoiceField(choices=const.POST_TYPES[:1])

    def clean(self):
        "Custom validator for the question"
        if not super(PostForm, self).is_valid():
            raise forms.ValidationError("Invalid form")
        
        if self.cleaned_data['tag_string'] == P_TAG:
            raise forms.ValidationError("Please create a different tag")

        tags = self.cleaned_data['tag_string'].split(' ')
        tags = map(string.strip, tags)
        shorts = map(lambda x:len(x)<3, tags)
        if any(shorts):
            raise forms.ValidationError("No tag may be shorter than 3 characters")

        if self.cleaned_data['content'] == P_CONTENT:
            raise forms.ValidationError("Please change the content")
        
        if self.cleaned_data['title'] == P_TITLE:
            raise forms.ValidationError("Please create a different title")

        post_type = int(self.cleaned_data['post_type'])
       
        if  post_type != const.POST_QUESTION:
            raise forms.ValidationError("Currently we only accept Questions in the Post type field")

        return self.cleaned_data
    
class ContentForm(forms.Form):
    """
    A form representing the body of simpler content answer/comment
    """
    content  = forms.CharField(max_length=5000)


