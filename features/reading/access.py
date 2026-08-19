"""app.py 모델에 순환 import 없이 접근한다."""
from extensions import db
from viewer_slug_utils import extract_viewer_slug


def model_named(name):
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        if getattr(cls, '__name__', None) == name:
            return cls
    raise RuntimeError(f'{name} 모델이 아직 등록되지 않았습니다.')


def get_child(child_id):
    if child_id is None:
        return None
    return model_named('Child').query.get(child_id)


def resolve_viewer_child(view_token):
    slug = extract_viewer_slug(view_token)
    if not slug:
        return None, None
    child = model_named('Child').query.filter_by(viewer_slug=slug).first()
    if not child:
        return None, None
    return child, slug
