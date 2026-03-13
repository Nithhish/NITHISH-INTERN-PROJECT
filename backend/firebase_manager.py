import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
from dotenv import load_dotenv

load_dotenv()

class FirebaseManager:
    def __init__(self):
        self.db = None
        self.bucket = None
        self.initialized = False
        
        service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
        
        try:
            cred = None
            if service_account_json:
                import json
                service_account_info = json.loads(service_account_json)
                cred = credentials.Certificate(service_account_info)
                print("[Firebase] Initializing from JSON environment variable")
            elif service_account_path and os.path.exists(service_account_path):
                cred = credentials.Certificate(service_account_path)
                print(f"[Firebase] Initializing from path: {service_account_path}")
            else:
                # Fallback: check for default filename in current or parent dir
                default_paths = ["firebase-service-account.json", "backend/firebase-service-account.json"]
                for p in default_paths:
                    if os.path.exists(p):
                        cred = credentials.Certificate(p)
                        print(f"[Firebase] Initializing from fallback path: {p}")
                        break

            if cred:
                firebase_admin.initialize_app(cred, {
                    'storageBucket': storage_bucket
                })
                self.db = firestore.client()
                self.bucket = storage.bucket()
                self.initialized = True
                print("[Firebase] Successfully initialized")
            else:
                print("[Firebase] Config missing. Provide FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_PATH in .env")
        except Exception as e:
            print(f"[Firebase] Initialization error: {e}")

    def upload_file(self, local_path, remote_path):
        """Uploads a file to Firebase Storage and returns the public URL."""
        if not self.initialized:
            return None
        
        try:
            blob = self.bucket.blob(remote_path)
            blob.upload_from_filename(local_path)
            # Make the blob public (optional, or use signed URLs)
            blob.make_public()
            return blob.public_url
        except Exception as e:
            print(f"[Firebase] Upload error: {e}")
            return None

    def save_session_data(self, session_id, data):
        """Saves session metadata to Firestore."""
        if not self.initialized:
            return False
            
        try:
            doc_ref = self.db.collection('sessions').document(str(session_id))
            doc_ref.set(data, merge=True)
            return True
        except Exception as e:
            print(f"[Firebase] Firestore error: {e}")
            return False

    def save_shot_metrics(self, session_id, shot_id, metrics):
        """Saves individual shot metrics to a subcollection in Firestore."""
        if not self.initialized:
            return False
            
        try:
            doc_ref = self.db.collection('sessions').document(str(session_id))\
                            .collection('shots').document(str(shot_id))
            doc_ref.set(metrics)
            return True
        except Exception as e:
            print(f"[Firebase] Firestore shot error: {e}")
            return False

    def create_player(self, player_id, name, email):
        """Syncs a player to Firestore."""
        if not self.initialized:
            return False
        try:
            doc_ref = self.db.collection('players').document(str(player_id))
            doc_ref.set({
                "name": name,
                "email": email,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            return True
        except Exception as e:
            print(f"[Firebase] Create player error: {e}")
            return False

    def get_player(self, player_id):
        """Retrieves a player from Firestore."""
        if not self.initialized:
            return None
        try:
            doc = self.db.collection('players').document(str(player_id)).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            print(f"[Firebase] Get player error: {e}")
            return None

    def list_players(self):
        """Lists all players from Firestore."""
        if not self.initialized:
            return []
        try:
            players = self.db.collection('players').stream()
            return [{"id": p.id, **p.to_dict()} for p in players]
        except Exception as e:
            print(f"[Firebase] List players error: {e}")
            return []

    def get_session_data(self, session_id):
        """Retrieves session metadata from Firestore."""
        if not self.initialized:
            return None
        try:
            doc = self.db.collection('sessions').document(str(session_id)).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            print(f"[Firebase] Get session error: {e}")
            return None

    def list_player_sessions(self, player_id):
        """Lists all sessions for a specific player from Firestore."""
        if not self.initialized:
            return []
        try:
            sessions = self.db.collection('sessions')\
                           .where('player_id', '==', player_id)\
                           .order_by('processed_at', direction=firestore.Query.DESCENDING)\
                           .stream()
            return [{"id": s.id, **s.to_dict()} for s in sessions]
        except Exception as e:
            print(f"[Firebase] List player sessions error: {e}")
            return []

    def get_shot_metrics(self, session_id):
        """Retrieves all shot metrics for a session from Firestore."""
        if not self.initialized:
            return []
        try:
            shots = self.db.collection('sessions').document(str(session_id))\
                        .collection('shots').stream()
            return [{"id": s.id, **s.to_dict()} for s in shots]
        except Exception as e:
            print(f"[Firebase] Get shot metrics error: {e}")
            return []

# Singleton instance
firebase_client = FirebaseManager()
