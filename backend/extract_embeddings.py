import os
import sys
import logging
import pickle
from pathlib import Path

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# Add backend directory to path
BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from flask import Flask, current_app
from extensions import db
from models import FaceEncoding, InstructorFaceEncoding, Student, User  # User model contains instructors
from config import Config
import numpy as np

logger = logging.getLogger(__name__)

# Import DeepFace for face embedding generation
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
    print("DeepFace imported successfully")
except ImportError as e:
    DEEPFACE_AVAILABLE = False
    print(f"DeepFace not available: {e}")

# DeepFace Configuration
DEEPFACE_MODEL = "Facenet512"  # Using FaceNet-512 model
DEEPFACE_DETECTOR = "opencv"   # Using OpenCV detector
DEEPFACE_DISTANCE_METRIC = "cosine"  # Distance metric for face comparison

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def create_app():
    """Create Flask application."""
    base_dir = Path(__file__).parent
    frontend_dir = base_dir / '..' / 'frontend'
    app = Flask(
        __name__,
        static_folder=str(frontend_dir / 'static'),
        template_folder=str(frontend_dir / 'templates')
    )
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)

    return app


def empty_face_data():
    """Return a fresh dictionary shaped like the cache payload."""
    return {
        'student_embeddings': [],
        'student_names': [],
        'student_ids': [],
        'instructor_embeddings': [],
        'instructor_names': [],
        'instructor_ids': []
    }


def load_existing_face_data(cache_file):
    """Load cached embeddings (if any) to support incremental extraction."""
    data = empty_face_data()
    if not cache_file.exists():
        return data

    try:
        with open(cache_file, 'rb') as f:
            cached = pickle.load(f)

        for key in data.keys():
            if key in cached:
                data[key] = cached[key]

        logger.info(f"Loaded existing cache from {cache_file}")
        return data
    except Exception as e:
        logger.warning(f"Failed to load existing cache, continuing with empty data: {e}")
        return data

def generate_face_embedding(image_path):
    """Generate face embedding using DeepFace with FaceNet-512"""
    if not DEEPFACE_AVAILABLE:
        logger.warning("DeepFace not available, using placeholder encoding")
        return np.zeros(512, dtype=np.float32)  # Return placeholder array

    try:
        logger.info(f"Generating face embedding for: {image_path}")

        # Try a sequence of detector backends: configured one, then retinaface, then mtcnn
        detectors_to_try = [DEEPFACE_DETECTOR]
        for alt in ("retinaface", "mtcnn"):
            if alt not in detectors_to_try:
                detectors_to_try.append(alt)

        for detector in detectors_to_try:
            logger.info(f"Attempting face detection/embedding with detector: {detector}")
            # First try to detect faces with this detector
            try:
                faces = DeepFace.extract_faces(
                    img_path=image_path,
                    detector_backend=detector,
                    enforce_detection=True,
                    align=True
                )
                if not faces or len(faces) == 0:
                    logger.warning(f"No faces detected with detector '{detector}'")
                    continue
                logger.info(f"Detected {len(faces)} face(s) using '{detector}'")
            except Exception as detect_error:
                logger.warning(f"Face detection failed with '{detector}': {detect_error}")
                continue

            # Try to obtain the embedding using the same detector
            try:
                embedding_result = DeepFace.represent(
                    img_path=image_path,
                    model_name=DEEPFACE_MODEL,
                    detector_backend=detector,
                    enforce_detection=True,
                    align=True
                )
            except Exception as rep_error:
                logger.warning(f"Embedding extraction failed with '{detector}': {rep_error}")
                continue

            if embedding_result and len(embedding_result) > 0:
                # embedding_result can be a list of dicts or a list of floats depending on DeepFace version
                first = embedding_result[0]
                if isinstance(first, dict) and 'embedding' in first:
                    emb = first['embedding']
                else:
                    emb = first
                face_embedding = np.array(emb, dtype=np.float32)
                logger.info(f"Successfully generated face embedding with '{detector}', dimension: {len(face_embedding)}")
                return face_embedding
            else:
                logger.warning(f"No face embedding extracted using '{detector}'")

        logger.warning("All detectors attempted, no embedding extracted")
        return None

    except Exception as e:
        logger.error(f"Error generating face embedding: {e}")
        return None

def process_student_encodings(student_embeddings, student_names, student_ids, skip_ids=None):
    """Process student face encodings and collect into lists, optionally skipping cached IDs."""
    logger.info("Starting to process student face encodings...")

    # Query face encodings that have image paths
    face_encodings = FaceEncoding.query.filter(
        FaceEncoding.image_path.isnot(None)
    ).all()

    logger.info(f"Found {len(face_encodings)} face encoding records with image paths")

    processed = 0
    successful = 0
    failed = 0
    skipped = 0
    skip_ids = set(skip_ids or [])

    for face_encoding in face_encodings:
        try:
            if skip_ids and face_encoding.student_id in skip_ids:
                skipped += 1
                continue

            # Construct full image path
            image_path = os.path.join(current_app.static_folder, face_encoding.image_path)

            if not os.path.exists(image_path):
                logger.warning(f"Image file not found: {image_path}")
                failed += 1
                continue

            # Generate new embedding
            embedding = generate_face_embedding(image_path)

            if embedding is not None:
                # Get student name (from Student model)
                student = Student.query.get(face_encoding.student_id)
                name = f"{student.first_name} {student.last_name}" if student else f"Student_{face_encoding.student_id}"
                student_embeddings.append(embedding)
                student_names.append(name)
                student_ids.append(face_encoding.student_id)  # Store the actual student ID
                logger.info(f"Successfully processed encoding for student {name} (ID: {face_encoding.student_id})")
                successful += 1
            else:
                logger.warning(f"Failed to generate embedding for student {face_encoding.student_id}")
                failed += 1

        except Exception as e:
            logger.error(f"Error processing face encoding for student {face_encoding.student_id}: {str(e)}")
            failed += 1

        processed += 1

    logger.info(f"Processed {processed} student encodings: {successful} successful, {failed} failed, {skipped} skipped")

def process_instructor_encodings(instructor_embeddings, instructor_names, instructor_ids, skip_ids=None):
    """Process instructor face encodings, optionally skipping IDs already cached."""
    logger.info("Starting to process instructor face encodings...")

    # Query instructor face encodings that have image paths
    instructor_encodings = InstructorFaceEncoding.query.filter(
        InstructorFaceEncoding.image_path.isnot(None)
    ).all()

    logger.info(f"Found {len(instructor_encodings)} instructor face encoding records with image paths")

    processed = 0
    successful = 0
    failed = 0
    skipped = 0
    skip_ids = set(skip_ids or [])

    for instructor_encoding in instructor_encodings:
        try:
            if skip_ids and instructor_encoding.instructor_id in skip_ids:
                skipped += 1
                continue

            # Construct full image path
            image_path = os.path.join(current_app.static_folder, instructor_encoding.image_path)

            if not os.path.exists(image_path):
                logger.warning(f"Image file not found: {image_path}")
                failed += 1
                continue

            # Generate new embedding
            embedding = generate_face_embedding(image_path)

            if embedding is not None:
                # Get instructor name (from User model where role='instructor')
                instructor = User.query.filter_by(id=instructor_encoding.instructor_id, role='instructor').first()
                name = f"{instructor.first_name} {instructor.last_name}" if instructor else f"Instructor_{instructor_encoding.instructor_id}"
                instructor_embeddings.append(embedding)
                instructor_names.append(name)
                instructor_ids.append(instructor_encoding.instructor_id)  # Store the actual instructor ID
                logger.info(f"Successfully processed encoding for instructor {name} (ID: {instructor_encoding.instructor_id})")
                successful += 1
            else:
                logger.warning(f"Failed to generate embedding for instructor {instructor_encoding.instructor_id}")
                failed += 1

        except Exception as e:
            logger.error(f"Error processing face encoding for instructor {instructor_encoding.instructor_id}: {str(e)}")
            failed += 1

        processed += 1

    logger.info(f"Processed {processed} instructor encodings: {successful} successful, {failed} failed, {skipped} skipped")

def main(mode='all'):
    """Extract embeddings and persist them to disk.

    mode:
        'all' - rebuild every embedding from scratch.
        'new' - only process IDs not found in the existing cache and append them.
    """
    global logger
    logger = setup_logging()

    mode = (mode or 'all').lower()
    if mode not in {'all', 'new'}:
        logger.warning(f"Unknown extraction mode '{mode}', defaulting to 'all'")
        mode = 'all'

    logger.info(f"Starting embedding extraction process (mode={mode})...")

    if not DEEPFACE_AVAILABLE:
        logger.error("DeepFace is not available. Please install it to extract embeddings.")
        return False

    app = create_app()

    with app.app_context():
        try:
            cache_dir = Path(__file__).parent / '..' / 'cache'
            cache_dir.mkdir(exist_ok=True)
            cache_file = cache_dir / 'face_encodings.pkl'

            if mode == 'new':
                face_data_seed = load_existing_face_data(cache_file)
            else:
                face_data_seed = empty_face_data()

            student_embeddings = face_data_seed['student_embeddings']
            student_names = face_data_seed['student_names']
            student_ids = face_data_seed['student_ids']
            instructor_embeddings = face_data_seed['instructor_embeddings']
            instructor_names = face_data_seed['instructor_names']
            instructor_ids = face_data_seed['instructor_ids']

            student_skip_ids = student_ids if mode == 'new' else None
            instructor_skip_ids = instructor_ids if mode == 'new' else None

            process_student_encodings(student_embeddings, student_names, student_ids, skip_ids=student_skip_ids)
            process_instructor_encodings(instructor_embeddings, instructor_names, instructor_ids, skip_ids=instructor_skip_ids)

            face_data = {
                'student_embeddings': student_embeddings,
                'student_names': student_names,
                'student_ids': student_ids,
                'instructor_embeddings': instructor_embeddings,
                'instructor_names': instructor_names,
                'instructor_ids': instructor_ids
            }

            with open(cache_file, 'wb') as f:
                pickle.dump(face_data, f)

            logger.info(f"Embeddings saved to {cache_file} (mode={mode})")
            logger.info("Embedding extraction process completed successfully")
            return True

        except Exception as e:
            logger.error(f"Embedding extraction failed: {str(e)}")
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)