import { initializeApp } from "firebase/app";
import { initializeFirestore, persistentLocalCache, persistentMultipleTabManager } from "firebase/firestore";
import { getStorage } from "firebase/storage";
import { getAuth } from "firebase/auth";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyCL3hUtmI3Uv7-lkg0K4h2NRN7lUWCWni4",
  authDomain: "nithish-hosh.firebaseapp.com",
  projectId: "nithish-hosh",
  storageBucket: "nithish-hosh.firebasestorage.app",
  messagingSenderId: "696612341167",
  appId: "1:696612341167:web:e471fb484445fa7f6d5b5a",
  measurementId: "G-CBBD3LR0PX"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const db = initializeFirestore(app, {
  localCache: persistentLocalCache({ tabManager: persistentMultipleTabManager() })
});
export const storage = getStorage(app);
export const auth = getAuth(app);


export default app;
