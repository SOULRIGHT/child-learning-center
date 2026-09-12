"""app.py 모델에 순환 import 없이 접근한다."""
from viewer_slug_utils import extract_viewer_slug


def loaded_app_attr(name):
    import sys
    for key in ('__main__', 'app'):
        mod = sys.modules.get(key)
        value = getattr(mod, name, None) if mod is not None else None
        if value is not None:
            return value
    raise RuntimeError(f'{name} is not available on the loaded app module')


def _mapped_class(cls):
    if cls is None:
        return None
    try:
        from sqlalchemy.orm import class_mapper
        from sqlalchemy.orm.exc import UnmappedClassError
        class_mapper(cls)
    except UnmappedClassError:
        return None
    return cls


def model_named(name):
    import sys
    found = None
    for key in ('app', '__main__'):
        mod = sys.modules.get(key)
        cls = _mapped_class(getattr(mod, name, None) if mod is not None else None)
        if cls is not None:
            found = cls
            break
    if found is None:
        raise RuntimeError(f'{name} 모델이 아직 등록되지 않았습니다.')
    return found


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
