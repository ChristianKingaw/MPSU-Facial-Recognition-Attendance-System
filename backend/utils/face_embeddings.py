import os
import pickle
from pathlib import Path

import numpy as np
from flask import current_app

from models import FaceEncoding, InstructorFaceEncoding, Student, User

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

DEEPFACE_MODEL = 'Facenet512'
DEEPFACE_DETECTOR = 'opencv'
EXPECTED_EMBEDDING_DIMS = 512


def _to_embedding_array(raw_embedding):
    if raw_embedding is None:
        return None
    try:
        embedding_array = np.asarray(raw_embedding, dtype=np.float32).reshape(-1)
    except Exception:
        return None
    if embedding_array.size != EXPECTED_EMBEDDING_DIMS:
        return None
    return embedding_array


def extract_embedding_bytes(image_path):
    """Extract one FaceNet-512 embedding from an image and return bytes."""
    if not DEEPFACE_AVAILABLE:
        return None

    detectors = [DEEPFACE_DETECTOR, 'retinaface', 'mtcnn']
    seen = set()
    detectors = [detector for detector in detectors if not (detector in seen or seen.add(detector))]

    for enforce_detection in (True, False):
        for detector in detectors:
            try:
                result = DeepFace.represent(
                    img_path=image_path,
                    model_name=DEEPFACE_MODEL,
                    detector_backend=detector,
                    enforce_detection=enforce_detection,
                    align=True
                )
            except Exception:
                continue

            if not result:
                continue

            first = result[0] if isinstance(result, list) else result
            raw_embedding = first.get('embedding') if isinstance(first, dict) else first
            embedding_array = _to_embedding_array(raw_embedding)
            if embedding_array is not None:
                return embedding_array.tobytes()

    return None


def _load_existing_cache(cache_path):
    if not cache_path.exists():
        return {
            'student_embeddings': [],
            'student_names': [],
            'student_ids': [],
            'instructor_embeddings': [],
            'instructor_names': [],
            'instructor_ids': []
        }

    try:
        with open(cache_path, 'rb') as cache_file:
            cache_data = pickle.load(cache_file)
        if isinstance(cache_data, dict):
            return {
                'student_embeddings': cache_data.get('student_embeddings', []) or [],
                'student_names': cache_data.get('student_names', []) or [],
                'student_ids': cache_data.get('student_ids', []) or [],
                'instructor_embeddings': cache_data.get('instructor_embeddings', []) or [],
                'instructor_names': cache_data.get('instructor_names', []) or [],
                'instructor_ids': cache_data.get('instructor_ids', []) or []
            }
    except Exception:
        pass

    return {
        'student_embeddings': [],
        'student_names': [],
        'student_ids': [],
        'instructor_embeddings': [],
        'instructor_names': [],
        'instructor_ids': []
    }


def _cache_path_from_config():
    configured_path = current_app.config.get('FACE_ENCODINGS_CACHE')
    if configured_path:
        return Path(configured_path)
    return Path(current_app.root_path).parent / 'cache' / 'face_encodings.pkl'


def sync_face_encoding_cache():
    """Regenerate cache from stored embeddings and preserve legacy cache-only entries."""
    student_rows = FaceEncoding.query.all()
    instructor_rows = InstructorFaceEncoding.query.all()

    student_ids_with_images = {row.student_id for row in student_rows if row.student_id is not None}
    instructor_ids_with_images = {row.instructor_id for row in instructor_rows if row.instructor_id is not None}

    student_name_map = {}
    if student_ids_with_images:
        students = Student.query.filter(Student.id.in_(student_ids_with_images)).all()
        student_name_map = {student.id: f'{student.first_name} {student.last_name}' for student in students}

    instructor_name_map = {}
    if instructor_ids_with_images:
        instructors = User.query.filter(User.id.in_(instructor_ids_with_images), User.role == 'instructor').all()
        instructor_name_map = {instructor.id: f'{instructor.first_name} {instructor.last_name}' for instructor in instructors}

    payload = {
        'student_embeddings': [],
        'student_names': [],
        'student_ids': [],
        'instructor_embeddings': [],
        'instructor_names': [],
        'instructor_ids': []
    }

    valid_student_ids = set()
    for row in student_rows:
        embedding_array = None
        if row.encoding_data:
            try:
                embedding_array = _to_embedding_array(np.frombuffer(row.encoding_data, dtype=np.float32))
            except Exception:
                embedding_array = None
        if embedding_array is None:
            continue
        valid_student_ids.add(row.student_id)
        payload['student_embeddings'].append(embedding_array)
        payload['student_names'].append(student_name_map.get(row.student_id, f'Student_{row.student_id}'))
        payload['student_ids'].append(row.student_id)

    valid_instructor_ids = set()
    for row in instructor_rows:
        embedding_array = None
        if row.encoding:
            try:
                embedding_array = _to_embedding_array(np.frombuffer(row.encoding, dtype=np.float32))
            except Exception:
                embedding_array = None
        if embedding_array is None:
            continue
        valid_instructor_ids.add(row.instructor_id)
        payload['instructor_embeddings'].append(embedding_array)
        payload['instructor_names'].append(instructor_name_map.get(row.instructor_id, f'Instructor_{row.instructor_id}'))
        payload['instructor_ids'].append(row.instructor_id)

    cache_path = _cache_path_from_config()
    existing_cache = _load_existing_cache(cache_path)

    legacy_student_ids = student_ids_with_images - valid_student_ids
    for embedding, name, student_id in zip(
        existing_cache.get('student_embeddings', []),
        existing_cache.get('student_names', []),
        existing_cache.get('student_ids', [])
    ):
        if student_id not in legacy_student_ids:
            continue
        embedding_array = _to_embedding_array(embedding)
        if embedding_array is None:
            continue
        payload['student_embeddings'].append(embedding_array)
        payload['student_names'].append(name or student_name_map.get(student_id, f'Student_{student_id}'))
        payload['student_ids'].append(student_id)

    legacy_instructor_ids = instructor_ids_with_images - valid_instructor_ids
    for embedding, name, instructor_id in zip(
        existing_cache.get('instructor_embeddings', []),
        existing_cache.get('instructor_names', []),
        existing_cache.get('instructor_ids', [])
    ):
        if instructor_id not in legacy_instructor_ids:
            continue
        embedding_array = _to_embedding_array(embedding)
        if embedding_array is None:
            continue
        payload['instructor_embeddings'].append(embedding_array)
        payload['instructor_names'].append(name or instructor_name_map.get(instructor_id, f'Instructor_{instructor_id}'))
        payload['instructor_ids'].append(instructor_id)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_suffix(cache_path.suffix + '.tmp')
    with open(temp_path, 'wb') as cache_file:
        pickle.dump(payload, cache_file)
    os.replace(temp_path, cache_path)

    return {
        'student_embeddings': len(payload['student_embeddings']),
        'instructor_embeddings': len(payload['instructor_embeddings']),
        'cache_path': str(cache_path)
    }
