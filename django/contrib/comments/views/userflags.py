from django.core.extensions import DjangoContext, load_and_render
from django.core.exceptions import Http404
from django.models.comments import comments, moderatordeletions, userflags
from django.views.decorators.auth import login_required
from django.utils.httpwrappers import HttpResponseRedirect
from django.conf.settings import SITE_ID

def flag(request, comment_id):
    """
    Flags a comment. Confirmation on GET, action on POST.

    Templates: `comments/flag_verify`, `comments/flag_done`
    Context:
        comment
            the flagged `comments.comments` object
    """
    try:
        comment = comments.get_object(pk=comment_id, site__id__exact=SITE_ID)
    except comments.CommentDoesNotExist:
        raise Http404
    if request.POST:
        userflags.flag(comment, request.user)
        return HttpResponseRedirect('%sdone/' % request.path)
    return load_and_render('comments/flag_verify', {'comment': comment}, context_instance=DjangoContext(request))
flag = login_required(flag)

def flag_done(request, comment_id):
    try:
        comment = comments.get_object(pk=comment_id, site__id__exact=SITE_ID)
    except comments.CommentDoesNotExist:
        raise Http404
    return load_and_render('comments/flag_done', {'comment': comment}, context_instance=DjangoContext(request))

def delete(request, comment_id):
    """
    Deletes a comment. Confirmation on GET, action on POST.

    Templates: `comments/delete_verify`, `comments/delete_done`
    Context:
        comment
            the flagged `comments.comments` object
    """
    try:
        comment = comments.get_object(pk=comment_id, site__id__exact=SITE_ID)
    except comments.CommentDoesNotExist:
        raise Http404
    if not comments.user_is_moderator(request.user):
        raise Http404
    if request.POST:
        # If the comment has already been removed, silently fail.
        if not comment.is_removed:
            comment.is_removed = True
            comment.save()
            m = moderatordeletions.ModeratorDeletion(None, request.user.id, comment.id, None)
            m.save()
        return HttpResponseRedirect('%sdone/' % request.path)
    return load_and_render('comments/delete_verify', {'comment': comment}, context_instance=DjangoContext(request))
delete = login_required(delete)

def delete_done(request, comment_id):
    try:
        comment = comments.get_object(pk=comment_id, site__id__exact=SITE_ID)
    except comments.CommentDoesNotExist:
        raise Http404
    return load_and_render('comments/delete_done', {'comment': comment}, context_instance=DjangoContext(request))
