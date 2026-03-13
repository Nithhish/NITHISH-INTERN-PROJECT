import { useState, useEffect, useRef } from 'react'
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
    AreaChart, Area
} from 'recharts'
import {
    Upload, User, Activity, AlertTriangle, ChevronRight,
    Trophy, Clock, Target, Play, Image, Video, X, Download,
    Zap, Shield, Eye, TrendingUp, CheckCircle2, Info,
    MessageSquare, Send, Cpu, Database, Smartphone, Camera, Layers, UserCheck, RefreshCw, WifiOff
} from 'lucide-react'
import axios from 'axios'
import { Capacitor } from '@capacitor/core'
import { db, auth } from './firebase'
import { collection, query, onSnapshot, orderBy, addDoc, serverTimestamp } from 'firebase/firestore'
import { Mail, AlertCircle } from 'lucide-react'

// Simple error handler for global issues
window.onerror = function(msg, url, lineNo, columnNo, error) {
    const errorDiv = document.getElementById('root');
    if (errorDiv && errorDiv.innerHTML === '') {
        errorDiv.innerHTML = `<div style="padding: 20px; color: #ff4d6d; text-align: center; font-family: sans-serif;">
            <h2 style="margin-bottom: 10px;">App Initialization Error</h2>
            <p style="font-size: 14px; opacity: 0.8;">${msg}</p>
            <button onclick="window.location.reload()" style="margin-top: 20px; padding: 10px 20px; background: #00ff88; border: none; border-radius: 8px; font-weight: bold; cursor: pointer;">Reload Application</button>
        </div>`;
    }
    return false;
};

// Custom hook for online status
function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
  return isOnline;
}


// Use dynamic API base if provided in URL (handy for testing tunnels), fallback to hardcoded
const getApiBase = () => {
    const urlParams = new URLSearchParams(window.location.search);
    const paramBase = urlParams.get('api_base');
    if (paramBase) return paramBase;
    
    // If we are visiting via web browser on a tunnel, use the current domain automatically
    if (typeof window !== 'undefined' && window.location.origin.includes('trycloudflare.com')) {
        return window.location.origin;
    }
    
    return 'https://merger-association-totals.trycloudflare.com';
};

const API_BASE = getApiBase();

// Bypass LocalTunnel warning screen for API requests
axios.defaults.headers.common['Bypass-Tunnel-Reminder'] = 'true';

/* ─────────────────────────────────────────
   Colour helpers
───────────────────────────────────────── */
const scoreColor = (v) => {
    if (v >= 80) return '#00ff88'
    if (v >= 60) return '#ffaa00'
    return '#ff4d6d'
}

const severityColor = (s) => {
    if (s === 'high') return '#ff4d6d'
    if (s === 'medium') return '#ffaa00'
    return '#00ff88'
}

/* ─────────────────────────────────────────
   Stat Badge
───────────────────────────────────────── */
function StatBadge({ icon: Icon, label, value, unit, color = '#00ff88', subtitle }) {
    return (
        <div style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 16,
            padding: '20px 22px',
            position: 'relative',
            overflow: 'hidden',
            transition: 'transform 0.2s, border-color 0.2s',
        }}
            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.borderColor = `${color}44` }}
            onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)' }}
        >
            {/* glow */}
            <div style={{ position: 'absolute', top: 0, right: 0, width: 80, height: 80, background: `radial-gradient(circle, ${color}18 0%, transparent 70%)`, pointerEvents: 'none' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, opacity: 0.55 }}>
                <Icon size={14} color={color} />
                <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#fff' }}>{label}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6 }}>
                <span style={{ fontSize: 40, fontWeight: 900, color: '#fff', lineHeight: 1 }}>{value}</span>
                {unit && <span style={{ fontSize: 13, color, fontWeight: 700, marginBottom: 4 }}>{unit}</span>}
            </div>
            {subtitle && <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginTop: 8 }}>{subtitle}</p>}
        </div>
    )
}

/* ─────────────────────────────────────────
   Injury Flag Row
───────────────────────────────────────── */
function InjuryRow({ flag }) {
    return (
        <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 14px',
            background: 'rgba(255,77,109,0.06)', borderRadius: 10,
            border: `1px solid ${severityColor(flag.severity)}33`
        }}>
            <AlertTriangle size={16} color={severityColor(flag.severity)} style={{ marginTop: 2, flexShrink: 0 }} />
            <div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 2 }}>
                    <span style={{ fontWeight: 700, fontSize: 12, color: '#fff' }}>{flag.type}</span>
                    <span style={{
                        fontSize: 9, fontWeight: 700, padding: '1px 7px', borderRadius: 99,
                        background: `${severityColor(flag.severity)}22`,
                        color: severityColor(flag.severity), textTransform: 'uppercase', letterSpacing: '0.06em'
                    }}>{flag.severity}</span>
                </div>
                <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', margin: 0 }}>{flag.message}</p>
            </div>
        </div>
    )
}

/* ─────────────────────────────────────────
   Media Preview
───────────────────────────────────────── */
function MediaPreview({ session }) {
    if (!session) return null
    const mediaPath = session.video_path
    const ext = mediaPath?.split('.').pop()?.toLowerCase() || ''
    const imageExts = ['jpg', 'jpeg', 'png', 'webp', 'bmp']
    const isImage = session.media_type === 'image' || imageExts.includes(ext)

    // Build URL from backend media endpoint
    const filename = mediaPath?.split(/[\\/]/).pop()
    const mediaUrl = `${API_BASE}/media/${filename}`

    if (isImage) {
        // Show annotated version if session is done
        const displayUrl = session.status === 'done' 
            ? `${API_BASE}/media/${filename.split('.').slice(0, -1).join('.')}_annotated.jpg` 
            : mediaUrl

        return (
            <div style={{ borderRadius: 14, overflow: 'hidden', background: '#0a0a0f', border: '1px solid rgba(255,255,255,0.08)', marginBottom: 20 }}>
                <img
                    src={displayUrl}
                    alt="Uploaded pose"
                    style={{ width: '100%', maxHeight: 280, objectFit: 'contain', display: 'block' }}
                    onError={e => { 
                        // Fallback to original if annotated not found
                        if (e.target.src !== mediaUrl) e.target.src = mediaUrl
                    }}
                />
            </div>
        )
    }

    return (
        <div style={{ borderRadius: 14, overflow: 'hidden', background: '#0a0a0f', border: '1px solid rgba(255,255,255,0.08)', marginBottom: 20 }}>
            <video
                src={mediaUrl}
                controls
                style={{ width: '100%', maxHeight: 220, display: 'block' }}
                onError={e => { e.target.style.display = 'none' }}
            />
        </div>
    )
}

/* ─────────────────────────────────────────
   GameIQ Workflow Diagram
───────────────────────────────────────── */
function WorkflowNode({ icon: Icon, title, items, color = '#00c8ff' }) {
    return (
        <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: `1px solid ${color}33`,
            borderRadius: 16,
            padding: 16,
            flex: 1,
            position: 'relative',
            minWidth: 160,
            boxShadow: `0 8px 32px ${color}10`
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                <div style={{ width: 30, height: 30, borderRadius: 8, background: `${color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Icon size={16} color={color} />
                </div>
                <h4 style={{ margin: 0, fontSize: 13, fontWeight: 800, color: '#fff' }}>{title}</h4>
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, color: 'rgba(255,255,255,0.6)', fontSize: 11, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {items.map((item, i) => <li key={i} style={{lineHeight: 1.3}}>{item}</li>)}
            </ul>
        </div>
    )
}

function WorkflowDiagram() {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '24px', background: 'rgba(255,255,255,0.02)', borderRadius: 20, border: '1px solid rgba(255,255,255,0.05)', flex: 1 }}>
            <div style={{ textAlign: 'center', marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, marginBottom: 8 }}>
                    <Activity size={28} color="#00ff88" />
                    <h2 style={{ fontSize: 24, fontWeight: 900, margin: 0, color: '#fff' }}>GameIQ AI</h2>
                </div>
                <p style={{ color: 'rgba(255,255,255,0.4)', margin: 0, fontSize: 13 }}>Cricket Performance Analysis Architecture</p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
                <WorkflowNode icon={Camera} title="Video Capture" items={['Mobile Camera', 'Tripod Camera']} color="#a78bfa" />
                <WorkflowNode icon={Upload} title="Video Upload" items={['Web App', 'Mobile App']} color="#00c8ff" />
                <WorkflowNode icon={Layers} title="Frame Processing" items={['Frame Extraction', 'Pre-Processing', 'Normalization']} color="#ffaa00" />
                <WorkflowNode icon={UserCheck} title="Player Detection" items={['Object Tracking', 'Player Cropping']} color="#00ff88" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
                <WorkflowNode icon={Activity} title="Pose Estimation" items={['YOLO Pose', 'MediaPipe', 'Keypoint Mapping']} color="#00ff88" />
                <WorkflowNode icon={Zap} title="Biomechanics Engine" items={['Bat Speed', 'Arm Angle', 'Hip Rotation', 'Knee Flexion']} color="#ffaa00" />
                <WorkflowNode icon={Target} title="AI Evaluation" items={['Technique Analysis', 'Injury Risk', 'Motion Analysis', 'Heatmaps']} color="#00c8ff" />
                <WorkflowNode icon={Trophy} title="Recommendations" items={['Training Tips', 'Correction Drills', 'Prevent Injury']} color="#a78bfa" />
            </div>

            <div style={{ 
                background: 'linear-gradient(90deg, rgba(255,170,0,0.1), rgba(0,255,136,0.1))',
                border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: '16px 24px', textAlign: 'center', marginTop: 8
            }}>
                <h4 style={{ margin: '0 0 6px', fontSize: 14, fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                    <RefreshCw size={16} color="#00ff88" /> Continuous Learning Feedback Loop
                </h4>
                <p style={{ margin: 0, fontSize: 12, color: 'rgba(255,255,255,0.5)' }}>More Data → Improved Models</p>
            </div>
        </div>
    )
}

/* ─────────────────────────────────────────
   AI Chatbot
───────────────────────────────────────── */
function AIChatbot({ session }) {
    const [isOpen, setIsOpen] = useState(false);
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState([
        { role: 'ai', text: 'Hi! I am ChatGPT. I am powered by GPT-4o and can analyze your cricket biomechanics or just chat about anything! How can I help you today?' }
    ]);

    useEffect(() => {
        if (session && session.status === 'done') {
            const numShots = session.shots?.length || 0;
            const avgScore = numShots > 0 ? (session.shots.reduce((a, s) => a + s.technique_score, 0) / numShots).toFixed(1) : '--';
            
            setMessages(prev => {
                // Check if we already greeted them about this session
                const alreadyGreeted = prev.some(m => m.text.includes(session.original_filename || session.id.toString()));
                if (alreadyGreeted) return prev;
                return [...prev, {
                    role: 'ai',
                    text: `I've analyzed "${session.original_filename || session.id}". I detected ${numShots} ${session.media_type === 'image' ? 'poses' : 'shots'} with an avg technique score of ${avgScore}. What would you like to know? You can ask about correction drills or injury risks!`
                }];
            });
        }
    }, [session?.id, session?.status]);

    const handleSend = async (e) => {
        e.preventDefault();
        if (!input.trim()) return;
        
        const userMsg = input.trim();
        setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
        setInput('');
        
        if (!isOnline) {
            setMessages(prev => [...prev, { role: 'ai', text: "I'm currently offline. Please reconnect to chat with me!" }]);
            return;
        }

        try {
            const res = await axios.post(`${API_BASE}/chat`, { 
                message: userMsg, 
                session_id: session?.id 
            });
            setMessages(prev => [...prev, { role: 'ai', text: res.data.response }]);
        } catch (err) {
            console.error("ChatGPT call failed", err);
            const msg = !isOnline ? "I'm offline. Please check your connection." : "I'm having trouble connecting to my AI core. Please ensure the OpenAI API Key is configured on the backend!";
            setMessages(prev => [...prev, { role: 'ai', text: msg }]);
        }
    }

    return (
        <>
            <div 
                style={{ position: 'fixed', bottom: 30, right: 30, zIndex: 999 }}
                onClick={() => setIsOpen(!isOpen)}
            >
                <div style={{
                    width: 60, height: 60, borderRadius: '50%', background: 'linear-gradient(135deg, #00c8ff, #005fa3)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
                    boxShadow: '0 8px 32px rgba(0,200,255,0.3)', border: '2px solid rgba(255,255,255,0.1)',
                    transition: 'transform 0.2s'
                }}
                onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.05)'}
                onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}>
                    {isOpen ? <X size={28} color="#fff" /> : <MessageSquare size={28} color="#fff" />}
                </div>
            </div>

            {isOpen && (
                <div style={{
                    position: 'fixed', bottom: 100, right: 30, zIndex: 998,
                    width: 360, height: 500, background: 'rgba(10,10,15,0.95)', backdropFilter: 'blur(20px)',
                    border: '1px solid rgba(255,255,255,0.08)', borderRadius: 24, boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
                    display: 'flex', flexDirection: 'column', overflow: 'hidden'
                }}>
                    <div style={{ padding: '16px 20px', background: 'rgba(0,200,255,0.1)', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#00c8ff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Cpu size={18} color="#000" />
                        </div>
                        <div>
                            <h4 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: '#fff' }}>ChatGPT</h4>
                            <p style={{ margin: 0, fontSize: 11, color: 'rgba(255,255,255,0.5)' }}>Powered by GPT-4o Vision</p>
                        </div>
                    </div>
                    
                    <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
                        {messages.map((m, i) => (
                            <div key={i} style={{ display: 'flex', gap: 8, alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
                                {m.role === 'ai' && (
                                    <div style={{ width: 28, height: 28, flexShrink: 0, borderRadius: '50%', background: 'rgba(0,200,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                        <Cpu size={14} color="#00c8ff" />
                                    </div>
                                )}
                                <div style={{
                                    background: m.role === 'user' ? 'linear-gradient(135deg, #00ff88, #00c860)' : 'rgba(255,255,255,0.05)',
                                    color: m.role === 'user' ? '#000' : '#fff',
                                    padding: '12px 16px', borderRadius: 16,
                                    borderTopLeftRadius: m.role === 'ai' ? 4 : 16,
                                    borderTopRightRadius: m.role === 'user' ? 4 : 16,
                                    fontSize: 13, lineHeight: 1.5,
                                    border: m.role === 'user' ? 'none' : '1px solid rgba(255,255,255,0.05)',
                                    whiteSpace: 'pre-line'
                                }}>
                                    {m.text}
                                </div>
                            </div>
                        ))}
                    </div>
                    
                    <form onSubmit={handleSend} style={{ padding: 16, borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', gap: 8, background: 'rgba(0,0,0,0.3)' }}>
                        <input 
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            placeholder="Ask ChatGPT..."
                            style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 99, padding: '10px 16px', color: '#fff', fontSize: 13, outline: 'none' }}
                        />
                        <button type="submit" disabled={!input.trim()} style={{
                            width: 40, height: 40, border: 'none', borderRadius: '50%', background: input.trim() ? '#00c8ff' : 'rgba(255,255,255,0.05)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: input.trim() ? 'pointer' : 'not-allowed',
                            color: input.trim() ? '#000' : 'rgba(255,255,255,0.3)', transition: 'background 0.2s'
                        }}>
                            <Send size={16} style={{ marginLeft: -2 }} />
                        </button>
                    </form>
                </div>
            )}
        </>
    )
}

/* ─────────────────────────────────────────
   Mailing List Component
   ───────────────────────────────────────── */
function MailingList() {
    const [email, setEmail] = useState('')
    const [status, setStatus] = useState('idle') // idle | loading | success | error

    const handleSubmit = async (e) => {
        e.preventDefault()
        if (!email) return
        
        setStatus('loading')
        try {
            await addDoc(collection(db, 'mailing_list'), {
                email: email,
                timestamp: serverTimestamp(),
                source: 'web_app'
            })
            setStatus('success')
            setEmail('')
            setTimeout(() => setStatus('idle'), 5000)
        } catch (err) {
            console.error('Mailing list error:', err)
            setStatus('error')
            setTimeout(() => setStatus('idle'), 5000)
        }
    }

    return (
        <div style={{
            background: 'rgba(255,255,255,0.03)',
            borderRadius: 16,
            padding: 20,
            border: '1px solid rgba(255,255,255,0.08)',
            marginTop: 16
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(0,255,136,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Mail size={16} color='#00ff88' />
                </div>
                <h4 style={{ margin: 0, fontSize: 13, fontWeight: 800, color: '#fff' }}>Join Mailing List</h4>
            </div>
            <p style={{ margin: '0 0 16px', fontSize: 11, color: 'rgba(255,255,255,0.4)', lineHeight: 1.4 }}>
                Get notified about new AI models and cricket training tips.
            </p>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <input 
                    type="email" 
                    placeholder="your@email.com"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    required
                    style={{
                        background: 'rgba(255,255,255,0.05)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: 10,
                        padding: '10px 14px',
                        color: '#fff',
                        fontSize: 12,
                        outline: 'none'
                    }}
                />
                <button 
                    type="submit" 
                    disabled={status === 'loading'}
                    style={{
                        background: status === 'success' ? '#00ff88' : status === 'error' ? '#ff4d6d' : 'linear-gradient(135deg, #00ff88, #00c8ff)',
                        color: '#000',
                        border: 'none',
                        borderRadius: 10,
                        padding: '10px',
                        fontSize: 12,
                        fontWeight: 800,
                        cursor: 'pointer',
                        transition: 'all 0.2s'
                    }}
                >
                    {status === 'loading' ? 'Joining...' : status === 'success' ? 'Joined! ✨' : status === 'error' ? 'Try Again' : 'Submit'}
                </button>
            </form>
        </div>
    )
}

/* ─────────────────────────────────────────
   Main App
   ───────────────────────────────────────── */
export default function App() {
    const [player, setPlayer] = useState(null)
    const [allPlayers, setAllPlayers] = useState([])
    const [sessions, setSessions] = useState([])
    const [selectedSession, setSelectedSession] = useState(null)
    const [isUploading, setIsUploading] = useState(false)
    const [uploadType, setUploadType] = useState(null) // 'video' | 'image'
    const [uploadLabel, setUploadLabel] = useState('')
    const [dragOver, setDragOver] = useState(false)
    const [uploadController, setUploadController] = useState(null)
    const isOnline = useOnlineStatus()
    const fileInputRef = useRef(null)
    const [windowWidth, setWindowWidth] = useState(window.innerWidth)

    useEffect(() => {
        const handleResize = () => setWindowWidth(window.innerWidth)
        window.addEventListener('resize', handleResize)
        return () => window.removeEventListener('resize', handleResize)
    }, [])

    const isMobile = windowWidth < 1024
    const isSmallMobile = windowWidth < 640


    const formatDate = (dateStr) => {
        const d = new Date(dateStr)
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    }


    const fetchSessions = async (playerId) => {
        try {
            const res = await axios.get(`${API_BASE}/players/${playerId}/sessions`)
            setSessions(res.data)
            localStorage.setItem(`sessions_${playerId}`, JSON.stringify(res.data))
            if (res.data.length > 0 && !selectedSession) {
                setSelectedSession(res.data[0])
            }
        } catch (err) {
            console.error('Failed to fetch sessions', err)
            const cached = localStorage.getItem(`sessions_${playerId}`)
            if (cached) {
                const data = JSON.parse(cached)
                setSessions(data)
                if (data.length > 0 && !selectedSession) setSelectedSession(data[0])
            }
        }
    }


    useEffect(() => {
        const initApp = async () => {
            try {
                // Load from cache first for instant UI
                const cachedPlayers = localStorage.getItem('allPlayers')
                if (cachedPlayers) {
                    try {
                        const ps = JSON.parse(cachedPlayers)
                        if (Array.isArray(ps) && ps.length > 0) {
                            setAllPlayers(ps)
                            setPlayer(ps[0])
                            const cachedSessions = localStorage.getItem(`sessions_${ps[0].id}`)
                            if (cachedSessions) setSessions(JSON.parse(cachedSessions))
                        }
                    } catch (e) {
                        console.warn("Cached data parse error", e)
                    }
                }

                const res = await axios.get(`${API_BASE}/players/`).catch(e => {
                    console.error("Fetch players failed", e);
                    // If everything fails and we have no cached players, we are stuck
                    return { data: [] };
                });

                if (res.data && res.data.length > 0) {
                    setAllPlayers(res.data)
                    setPlayer(res.data[0])
                    localStorage.setItem('allPlayers', JSON.stringify(res.data))
                    fetchSessions(res.data[0].id)
                } else if (!cachedPlayers) {
                    // Only try to create a new player if we have no cached player and no remote players
                    try {
                        const np = await axios.post(`${API_BASE}/players/`, { 
                            name: 'Pro Cricketer', 
                            email: `player_${Math.floor(Math.random()*1000)}@cricket.ai` 
                        })
                        setAllPlayers([np.data])
                        setPlayer(np.data)
                        localStorage.setItem('allPlayers', JSON.stringify([np.data]))
                        fetchSessions(np.data.id)
                    } catch (e) {
                        console.error("Failed to create default player", e);
                    }
                }
            } catch (err) {
                console.error('Critical init app error', err)
            }
        }

        initApp()
    }, [])
    
    const handlePlayerChange = async (e) => {
        const val = e.target.value;
        if (val === 'new') {
            const name = prompt("Enter new player name:");
            if (!name) return;
            const res = await axios.post(`${API_BASE}/players/`, { name, email: `${name.replace(/\s+/g,'').toLowerCase()}@cricket.ai` });
            setAllPlayers(prev => [...prev, res.data]);
            setPlayer(res.data);
            fetchSessions(res.data.id);
        } else {
            const p = allPlayers.find(x => x.id.toString() === val);
            if (p) {
                setPlayer(p);
                fetchSessions(p.id);
            }
        }
    }

    // Real-time Firebase Sync Listener
    useEffect(() => {
        if (!player) return;
        try {
            const q = query(collection(db, "sessions"), orderBy("processed_at", "desc"));
            const unsubscribe = onSnapshot(q, (snapshot) => {
                const fbSessions = snapshot.docs.map(doc => ({ 
                    id: doc.id, 
                    ...doc.data(),
                    source: 'cloud'
                }));
                if (fbSessions.length > 0) {
                    console.log("Real-time update from Firebase:", fbSessions.length, "sessions found");
                }
            }, (err) => {
                console.warn("Firebase listener error (likely missing config):", err.message);
            });
            return () => unsubscribe();
        } catch (e) {
            console.error("Firebase init failed:", e);
        }
    }, [player]);


    const pollSessionStatus = (sessionId, playerId) => {
        const iv = setInterval(async () => {
            try {
                const res = await axios.get(`${API_BASE}/sessions/${sessionId}/status`)
                if (res.data.status === 'done') {
                    clearInterval(iv)
                    setIsUploading(false)
                    setUploadType(null)
                    await fetchSessions(playerId)
                    // select the new session
                    const sr = await axios.get(`${API_BASE}/sessions/${sessionId}`)
                    setSelectedSession(sr.data)
                } else if (res.data.status === 'error') {
                    clearInterval(iv)
                    setIsUploading(false)
                    setUploadType(null)
                    alert('Processing failed. Please try again.')
                }
            } catch {
                clearInterval(iv)
                setIsUploading(false)
                setUploadType(null)
            }
        }, 2500)
    }

    const handleFileUpload = async (file, originalTypeGuess) => {
        if (!file || !player) return
        
        if (!isOnline) {
            alert("You are currently offline. Please reconnect to upload and analyze media.");
            return;
        }
        
        // Better mobile extension handling
        const extMatch = file.name.match(/\.([^.]+)$/);
        const ext = extMatch ? extMatch[1].toLowerCase() : '';
        const isImage = file.type.startsWith('image/') || ['jpg', 'jpeg', 'png', 'webp', 'bmp'].includes(ext);
        const type = isImage ? 'image' : 'video';

        setIsUploading(true)
        setUploadType(type)
        setUploadLabel(file.name || 'Mobile Upload')

        const formData = new FormData()
        formData.append('file', file)

        const endpoint = type === 'image'
            ? `${API_BASE}/upload-image/${player.id}`
            : `${API_BASE}/upload/${player.id}`

        const controller = new AbortController()
        setUploadController(controller)

        try {
            const res = await axios.post(endpoint, formData, { signal: controller.signal })
            await fetchSessions(player.id)
            pollSessionStatus(res.data.session_id, player.id)
        } catch (err) {
            if (axios.isCancel(err)) {
                console.log('Upload canceled');
            } else {
                const msg = err?.response?.data?.detail || 'Upload failed. Is the backend running?'
                alert(msg)
            }
            setIsUploading(false)
            setUploadType(null)
            setUploadController(null)
        }
    }

    const onFileChange = (e) => {
        const file = e.target.files[0]
        if (!file) return
        const ext = file.name.split('.').pop().toLowerCase()
        const type = ['jpg', 'jpeg', 'png', 'webp', 'bmp'].includes(ext) ? 'image' : 'video'
        handleFileUpload(file, type)
        e.target.value = ''
    }

    const onDrop = (e) => {
        e.preventDefault()
        setDragOver(false)
        const file = e.dataTransfer.files[0]
        if (!file) return
        const ext = file.name.split('.').pop().toLowerCase()
        const type = ['jpg', 'jpeg', 'png', 'webp', 'bmp'].includes(ext) ? 'image' : 'video'
        handleFileUpload(file, type)
    }

    /* ── derived stats ── */
    const shots = selectedSession?.shots || []
    const avgTech = shots.length ? shots.reduce((a, s) => a + s.technique_score, 0) / shots.length : 0
    const avgStab = shots.length ? shots.reduce((a, s) => a + s.stability_deviation, 0) / shots.length : 0
    const avgSpeed = shots.length ? shots.reduce((a, s) => a + s.swing_speed_max, 0) / shots.length : 0
    const totalRisks = shots.reduce((a, s) => a + s.injury_flags.length, 0)
    const allFlags = shots.flatMap(s => s.injury_flags)
    const isImage = selectedSession?.media_type === 'image'

    const radarData = shots.length > 0
        ? Object.keys(shots[0]?.score_breakdown || {}).map(k => ({
            subject: k.charAt(0).toUpperCase() + k.slice(1).replace('_', ' '),
            value: shots.reduce((a, s) => a + (s.score_breakdown[k] || 0), 0) / shots.length,
            fullMark: 100
        }))
        : []

    const anglesData = shots.map(s => ({
        name: `Shot ${s.shot_id}`,
        elbow: +(s.angle_metrics?.elbow || 0).toFixed(1),
        knee: +(s.angle_metrics?.knee || 0).toFixed(1),
    }))

    const speedData = shots.map(s => ({
        name: `Shot ${s.shot_id}`,
        speed: +(s.swing_speed_max || 0).toFixed(1),
        score: +(s.technique_score || 0).toFixed(1),
    }))

    /* ── styles ── */
    const card = {
        background: 'rgba(255,255,255,0.03)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 20,
        padding: 24,
    }

    const tooltipStyle = {
        contentStyle: { backgroundColor: '#0e0e14', border: '1px solid #222', borderRadius: 10, fontSize: 12 },
        itemStyle: { fontSize: 12 },
    }

    return (
        <div style={{ 
            minHeight: '100vh', 
            padding: isSmallMobile ? '16px 12px' : '24px 20px', 
            maxWidth: 1600, 
            margin: '0 auto', 
            fontFamily: 'Inter, system-ui, sans-serif', 
            color: '#fff',
            overflowX: 'hidden'
        }}>

            {/* ── Header ── */}
            <header style={{ 
                display: 'flex', 
                flexDirection: isSmallMobile ? 'column' : 'row',
                justifyContent: 'space-between', 
                alignItems: isSmallMobile ? 'flex-start' : 'center', 
                marginBottom: isSmallMobile ? 24 : 32,
                gap: 16
            }}>
                <div>
                    <h1 style={{ fontSize: 28, fontWeight: 900, margin: 0, letterSpacing: '-0.5px' }}>
                        Cricket<span style={{ color: '#00ff88' }}>AI</span> Analysis
                    </h1>
                    <p style={{ margin: '4px 0 0', fontSize: 13, color: 'rgba(255,255,255,0.4)', display: 'flex', alignItems: 'center', gap: 6 }}>
                        Biomechanical insights from video &amp; image uploads
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 99, background: 'rgba(0,200,255,0.1)', color: '#00c8ff', fontSize: 10, fontWeight: 800 }}>
                            <Database size={10} /> FIREBASE DB
                        </span>
                        {!isOnline && (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 99, background: 'rgba(255,77,109,0.1)', color: '#ff4d6d', fontSize: 10, fontWeight: 800 }}>
                                <WifiOff size={10} /> OFFLINE MODE
                            </span>
                        )}
                    </p>

                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(255,255,255,0.05)', padding: '8px 16px 8px 8px', borderRadius: 99, border: '1px solid rgba(255,255,255,0.08)' }}>
                    <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'linear-gradient(135deg,#00ff88,#00c8ff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, color: '#000', fontSize: 15 }}>
                        {player?.name?.[0] || <User size={18} />}
                    </div>
                    <select 
                        value={player?.id || ''} 
                        onChange={handlePlayerChange}
                        style={{ background: 'transparent', color: '#fff', border: 'none', outline: 'none', fontWeight: 600, fontSize: 14, cursor: 'pointer', appearance: 'none' }}
                    >
                        {allPlayers.map(p => <option key={p.id} value={p.id} style={{color: '#000'}}>{p.name}</option>)}
                        <option value="new" style={{color: '#000', fontWeight: 'bold'}}>+ New Player</option>
                    </select>
                </div>
            </header>

            <div style={{ 
                display: 'grid', 
                gridTemplateColumns: isMobile ? '1fr' : '300px 1fr', 
                gap: 20 
            }}>

                {/* ── Sidebar ── */}
                <aside style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

                    {/* Upload Card */}
                    <div style={{ ...card }}>
                        <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Upload size={16} color='#00ff88' /> Upload Media
                        </h3>

                        {/* Drop zone */}
                        <div
                            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                            onDragLeave={() => setDragOver(false)}
                            onDrop={onDrop}
                            onClick={() => !isUploading && fileInputRef.current?.click()}
                            style={{
                                border: `2px dashed ${dragOver ? '#00ff88' : 'rgba(255,255,255,0.12)'}`,
                                borderRadius: 14,
                                padding: '28px 16px',
                                textAlign: 'center',
                                cursor: isUploading ? 'not-allowed' : 'pointer',
                                transition: 'border-color 0.2s, background 0.2s',
                                background: dragOver ? 'rgba(0,255,136,0.04)' : 'transparent',
                            }}
                        >
                            {isUploading ? (
                                <div>
                                    <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
                                        {uploadType === 'image' ? <Image size={28} color='#00c8ff' /> : <Video size={28} color='#00ff88' />}
                                    </div>
                                    <p style={{ margin: '0 0 6px', fontSize: 11, fontWeight: 700, color: uploadType === 'image' ? '#00c8ff' : '#00ff88' }}>
                                        Analysing {uploadType === 'image' ? 'Image' : 'Video'}…
                                    </p>
                                    <p style={{ margin: 0, fontSize: 10, color: 'rgba(255,255,255,0.3)', wordBreak: 'break-all' }}>{uploadLabel}</p>
                                    <div style={{ marginTop: 12, height: 3, borderRadius: 8, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                                        <div style={{
                                            height: '100%', width: '60%', borderRadius: 8,
                                            background: uploadType === 'image' ? 'linear-gradient(90deg,#00c8ff,#005fa3)' : 'linear-gradient(90deg,#00ff88,#00c860)',
                                            animation: 'pulse-bar 1.5s ease-in-out infinite'
                                        }} />
                                    </div>
                                    <button 
                                        onClick={(e) => { e.stopPropagation(); uploadController?.abort() }}
                                        style={{ marginTop: 16, padding: '6px 16px', background: 'rgba(255,77,109,0.1)', color: '#ff4d6d', border: '1px solid rgba(255,77,109,0.2)', borderRadius: 8, fontSize: 11, fontWeight: 'bold', cursor: 'pointer' }}
                                    >Cancel</button>
                                </div>
                            ) : (
                                <>
                                    <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginBottom: 12 }}>
                                        <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(0,255,136,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                            <Video size={20} color='#00ff88' />
                                        </div>
                                        <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(0,200,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                            <Image size={20} color='#00c8ff' />
                                        </div>
                                    </div>
                                    <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.7)' }}>Drop video or image here</p>
                                    <p style={{ margin: 0, fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>MP4, MOV, AVI  ·  JPG, PNG, WEBP</p>
                                </>
                            )}
                        </div>

                        <input
                            ref={fileInputRef}
                            type='file'
                            style={{ display: 'none' }}
                            accept='video/*,image/*,.jpg,.jpeg,.png,.webp,.bmp,.mp4,.mov,.avi,.mkv'
                            onChange={onFileChange}
                            disabled={isUploading}
                        />

                        {/* Quick-pick buttons */}
                        {!isUploading && (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
                                <button
                                    id='btn-upload-video'
                                    onClick={() => { fileInputRef.current.accept = 'video/*'; fileInputRef.current.click() }}
                                    style={{ padding: '9px 0', borderRadius: 10, border: '1px solid rgba(0,255,136,0.25)', background: 'rgba(0,255,136,0.06)', color: '#00ff88', fontSize: 11, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}
                                >
                                    <Video size={13} /> Video
                                </button>
                                <button
                                    id='btn-upload-image'
                                    onClick={() => { fileInputRef.current.accept = 'image/*'; fileInputRef.current.click() }}
                                    style={{ padding: '9px 0', borderRadius: 10, border: '1px solid rgba(0,200,255,0.25)', background: 'rgba(0,200,255,0.06)', color: '#00c8ff', fontSize: 11, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}
                                >
                                    <Image size={13} /> Image
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Sessions List */}
                    <div style={{ ...card, flex: 1 }}>
                        <h3 style={{ margin: '0 0 14px', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Clock size={16} color='rgba(255,255,255,0.4)' /> Sessions
                        </h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 480, overflowY: 'auto' }}>
                            {sessions.length > 0 ? sessions.map(s => (
                                <div
                                    key={s.id}
                                    id={`session-${s.id}`}
                                    onClick={() => setSelectedSession(s)}
                                    style={{
                                        padding: '12px 14px', borderRadius: 12, cursor: 'pointer',
                                        border: `1px solid ${selectedSession?.id === s.id ? '#00ff88' : 'rgba(255,255,255,0.06)'}`,
                                        background: selectedSession?.id === s.id ? 'rgba(0,255,136,0.07)' : 'rgba(255,255,255,0.02)',
                                        transition: 'all 0.15s',
                                        display: 'flex', alignItems: 'center', gap: 10
                                    }}
                                >
                                    <div style={{ width: 32, height: 32, borderRadius: 8, background: s.media_type === 'image' ? 'rgba(0,200,255,0.1)' : 'rgba(0,255,136,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                        {s.media_type === 'image' ? <Image size={15} color='#00c8ff' /> : <Video size={15} color='#00ff88' />}
                                    </div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <p style={{ margin: 0, fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                            {s.original_filename || `Session #${s.id}`}
                                        </p>
                                        <p style={{ margin: '2px 0 0', fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>{formatDate(s.processed_at)}</p>
                                    </div>
                                    <div style={{ flexShrink: 0 }}>
                                        {s.status === 'processing' && <span style={{ fontSize: 9, background: 'rgba(255,170,0,0.15)', color: '#ffaa00', borderRadius: 99, padding: '2px 7px', fontWeight: 700 }}>PROCESSING</span>}
                                        {s.status === 'done' && <ChevronRight size={14} color={selectedSession?.id === s.id ? '#00ff88' : 'rgba(255,255,255,0.2)'} />}
                                        {s.status === 'error' && <span style={{ fontSize: 9, background: 'rgba(255,77,109,0.15)', color: '#ff4d6d', borderRadius: 99, padding: '2px 7px', fontWeight: 700 }}>ERROR</span>}
                                    </div>
                                </div>
                            )) : (
                                <p style={{ textAlign: 'center', fontSize: 12, color: 'rgba(255,255,255,0.25)', padding: '24px 0' }}>No sessions yet. Upload a video or image!</p>
                            )}
                        </div>
                    </div>

                    <MailingList />
                </aside>

                {/* ── Main Panel ── */}
                <main style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                    {selectedSession ? (
                        <>
                            {/* Session Meta Banner */}
                            <div style={{ ...card, display: 'flex', gap: 14, alignItems: 'center', padding: '16px 22px' }}>
                                <div style={{ width: 44, height: 44, borderRadius: 12, background: isImage ? 'rgba(0,200,255,0.12)' : 'rgba(0,255,136,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                    {isImage ? <Image size={22} color='#00c8ff' /> : <Video size={22} color='#00ff88' />}
                                </div>
                                <div style={{ flex: 1 }}>
                                    <p style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>{selectedSession.original_filename || `Session #${selectedSession.id}`}</p>
                                    <p style={{ margin: '2px 0 0', fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>
                                        {isImage ? 'Pose Snapshot Analysis' : 'Video Biomechanical Analysis'} · {formatDate(selectedSession.processed_at)} · {shots.length} {isImage ? 'pose' : 'shot'}{shots.length !== 1 ? 's' : ''} detected
                                    </p>
                                </div>
                                <span style={{
                                    padding: '5px 14px', borderRadius: 99, fontSize: 11, fontWeight: 700,
                                    background: selectedSession.status === 'done' ? 'rgba(0,255,136,0.12)' : selectedSession.status === 'error' ? 'rgba(255,77,109,0.12)' : 'rgba(255,170,0,0.12)',
                                    color: selectedSession.status === 'done' ? '#00ff88' : selectedSession.status === 'error' ? '#ff4d6d' : '#ffaa00'
                                }}>
                                    {selectedSession.status.toUpperCase()}
                                </span>
                            </div>

                            {/* Media Preview */}
                            <MediaPreview session={selectedSession} />

                            {shots.length > 0 ? (
                                <>
                                    {/* KPI Cards */}
                                    <div style={{ 
                                        display: 'grid', 
                                        gridTemplateColumns: isSmallMobile ? '1fr' : (windowWidth < 1280 ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)'), 
                                        gap: 14 
                                    }}>
                                        <StatBadge icon={Trophy} label='Tech Score' value={avgTech.toFixed(1)} color={scoreColor(avgTech)} subtitle='Overall technique quality' />
                                        <StatBadge icon={RefreshCw} label='Hip Rotation' value={(shots[0]?.angle_metrics?.hip_rotation || 0).toFixed(1)} unit='°' color='#ffaa00' subtitle='Hip-Shoulder Separation' />
                                        <StatBadge icon={Shield} label='Stability' value={avgStab < 0.05 ? 'Stable' : 'Unstable'} unit='' color={avgStab < 0.05 ? '#00ff88' : '#ffaa00'} subtitle={`Deviation: ${avgStab.toFixed(4)}`} />
                                        <StatBadge icon={AlertTriangle} label='Injury Risks' value={totalRisks} color={totalRisks > 0 ? '#ff4d6d' : '#00ff88'} subtitle={totalRisks > 0 ? 'Review flags below' : 'No risks detected'} />
                                    </div>

                                    {/* Heatmap Simulation */}
                                    <div style={{ ...card, padding: '20px' }}>
                                        <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <Layers size={16} color='#00ff88' /> Motion Intensity Heatmap
                                        </h3>
                                        <div style={{ 
                                            height: 100, 
                                            background: 'radial-gradient(circle at 30% 50%, rgba(0,255,136,0.2), transparent 40%), radial-gradient(circle at 70% 50%, rgba(0,200,255,0.2), transparent 45%)',
                                            borderRadius: 12,
                                            border: '1px solid rgba(255,255,255,0.05)',
                                            position: 'relative',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            overflow: 'hidden'
                                        }}>
                                            <p style={{ margin: 0, fontSize: 11, color: 'rgba(255,255,255,0.3)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Kinematic Sequence Intensity</p>
                                            {/* simulate heatmap spots */}
                                            <div style={{ position: 'absolute', top: '40%', left: '25%', width: 20, height: 20, borderRadius: '50%', background: '#00ff88', filter: 'blur(15px)', opacity: 0.6 }} />
                                            <div style={{ position: 'absolute', top: '50%', left: '35%', width: 30, height: 30, borderRadius: '50%', background: '#ffaa00', filter: 'blur(20px)', opacity: 0.5 }} />
                                            <div style={{ position: 'absolute', top: '45%', left: '65%', width: 25, height: 25, borderRadius: '50%', background: '#00c8ff', filter: 'blur(18px)', opacity: 0.6 }} />
                                        </div>
                                    </div>

                                    {/* Charts row */}
                                    <div style={{ 
                                        display: 'grid', 
                                        gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', 
                                        gap: 16 
                                    }}>
                                        {/* Angle Chart */}
                                        <div style={card}>
                                            <h3 style={{ margin: '0 0 18px', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <Activity size={16} color='#00ff88' />
                                                {isImage ? 'Joint Angles (Pose)' : 'Impact Angle Consistency'}
                                            </h3>
                                            <div style={{ height: 220 }}>
                                                <ResponsiveContainer width='100%' height='100%'>
                                                    <AreaChart data={anglesData}>
                                                        <defs>
                                                            <linearGradient id='gElbow' x1='0' y1='0' x2='0' y2='1'>
                                                                <stop offset='5%' stopColor='#00ff88' stopOpacity={0.3} />
                                                                <stop offset='95%' stopColor='#00ff88' stopOpacity={0} />
                                                            </linearGradient>
                                                        </defs>
                                                        <CartesianGrid strokeDasharray='3 3' stroke='rgba(255,255,255,0.05)' />
                                                        <XAxis dataKey='name' stroke='#555' fontSize={10} />
                                                        <YAxis stroke='#555' fontSize={10} domain={['auto', 'auto']} />
                                                        <Tooltip {...tooltipStyle} />
                                                        <Area type='monotone' dataKey='elbow' stroke='#00ff88' fillOpacity={1} fill='url(#gElbow)' strokeWidth={2.5} name='Elbow°' />
                                                        <Area type='monotone' dataKey='knee' stroke='#ffaa00' fill='transparent' strokeWidth={2} strokeDasharray='5 5' name='Knee°' />
                                                    </AreaChart>
                                                </ResponsiveContainer>
                                            </div>
                                            <div style={{ display: 'flex', gap: 18, justifyContent: 'center', marginTop: 10 }}>
                                                <span style={{ fontSize: 10, color: '#00ff88', display: 'flex', alignItems: 'center', gap: 4, fontWeight: 700 }}><span style={{ width: 14, height: 2, background: '#00ff88', borderRadius: 2, display: 'inline-block' }} /> Elbow°</span>
                                                <span style={{ fontSize: 10, color: '#ffaa00', display: 'flex', alignItems: 'center', gap: 4, fontWeight: 700 }}><span style={{ width: 14, height: 2, background: '#ffaa00', borderRadius: 2, display: 'inline-block' }} /> Knee°</span>
                                            </div>
                                        </div>

                                        {/* Radar / Score Breakdown */}
                                        <div style={card}>
                                            <h3 style={{ margin: '0 0 18px', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <Target size={16} color='#ffaa00' /> Technique Matrix
                                            </h3>
                                            <div style={{ height: 220 }}>
                                                <ResponsiveContainer width='100%' height='100%'>
                                                    <RadarChart cx='50%' cy='50%' outerRadius='75%' data={radarData}>
                                                        <PolarGrid stroke='rgba(255,255,255,0.06)' />
                                                        <PolarAngleAxis dataKey='subject' stroke='rgba(255,255,255,0.4)' fontSize={10} />
                                                        <PolarRadiusAxis angle={30} domain={[0, 100]} axisLine={false} tick={false} />
                                                        <Radar name='Score' dataKey='value' stroke='#ffaa00' fill='#ffaa00' fillOpacity={0.3} strokeWidth={2} />
                                                    </RadarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Speed / score bar chart (video only) */}
                                    {!isImage && speedData.length > 0 && (
                                        <div style={card}>
                                            <h3 style={{ margin: '0 0 18px', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <TrendingUp size={16} color='#00c8ff' /> Shot-by-Shot Performance
                                            </h3>
                                            <div style={{ height: 180 }}>
                                                <ResponsiveContainer width='100%' height='100%'>
                                                    <BarChart data={speedData} barGap={4}>
                                                        <CartesianGrid strokeDasharray='3 3' stroke='rgba(255,255,255,0.05)' />
                                                        <XAxis dataKey='name' stroke='#555' fontSize={10} />
                                                        <YAxis stroke='#555' fontSize={10} />
                                                        <Tooltip {...tooltipStyle} />
                                                        <Bar dataKey='speed' name='Speed (deg/s)' fill='#00c8ff' radius={[5, 5, 0, 0]} />
                                                        <Bar dataKey='score' name='Tech Score' fill='#00ff88' radius={[5, 5, 0, 0]} />
                                                    </BarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </div>
                                    )}

                                    {/* Score Breakdown Cards */}
                                    <div style={card}>
                                        <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <Eye size={16} color='#a78bfa' /> Score Breakdown
                                        </h3>
                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
                                            {Object.entries(shots[0]?.score_breakdown || {}).map(([k]) => {
                                                const avg = shots.reduce((a, s) => a + (s.score_breakdown[k] || 0), 0) / shots.length
                                                const label = k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, ' ')
                                                const color = scoreColor(avg)
                                                return (
                                                    <div key={k} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 12, padding: '14px 16px', border: `1px solid ${color}22` }}>
                                                        <p style={{ margin: '0 0 8px', fontSize: 11, color: 'rgba(255,255,255,0.5)', fontWeight: 700 }}>{label}</p>
                                                        <p style={{ margin: '0 0 8px', fontSize: 26, fontWeight: 900, color }}>{avg.toFixed(1)}</p>
                                                        <div style={{ height: 4, borderRadius: 4, background: 'rgba(255,255,255,0.08)' }}>
                                                            <div style={{ height: '100%', width: `${avg}%`, borderRadius: 4, background: color, transition: 'width 1s ease' }} />
                                                        </div>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    </div>

                                    {/* Injury Flags */}
                                    <div style={card}>
                                        <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <AlertTriangle size={16} color={totalRisks > 0 ? '#ff4d6d' : '#00ff88'} /> Injury Risk Assessment
                                        </h3>
                                        {allFlags.length > 0 ? (
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                                                {allFlags.map((f, i) => <InjuryRow key={i} flag={f} />)}
                                            </div>
                                        ) : (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px', background: 'rgba(0,255,136,0.05)', border: '1px solid rgba(0,255,136,0.15)', borderRadius: 12 }}>
                                                <CheckCircle2 size={20} color='#00ff88' />
                                                <div>
                                                    <p style={{ margin: 0, fontWeight: 700, fontSize: 13, color: '#00ff88' }}>All Clear</p>
                                                    <p style={{ margin: 0, fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>No biomechanical injury risks detected in this session.</p>
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    {/* Shot Details Table */}
                                    {shots.length > 0 && (
                                        <div style={card}>
                                            <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <Info size={16} color='rgba(255,255,255,0.4)' /> Shot Details
                                            </h3>
                                            <div style={{ overflowX: 'auto' }}>
                                                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                                                    <thead>
                                                        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                                                            {['Shot', 'Tech Score', 'Speed (deg/s)', 'Duration (s)', 'Elbow°', 'Knee°', 'Risks'].map(h => (
                                                                <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                                                            ))}
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {shots.map(s => (
                                                            <tr key={s.shot_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                                                <td style={{ padding: '10px 12px', fontWeight: 700 }}>#{s.shot_id}</td>
                                                                <td style={{ padding: '10px 12px', color: scoreColor(s.technique_score), fontWeight: 700 }}>{s.technique_score.toFixed(1)}</td>
                                                                <td style={{ padding: '10px 12px', color: 'rgba(255,255,255,0.7)' }}>{s.swing_speed_max.toFixed(0)}</td>
                                                                <td style={{ padding: '10px 12px', color: 'rgba(255,255,255,0.7)' }}>{s.swing_duration.toFixed(3)}</td>
                                                                <td style={{ padding: '10px 12px', color: '#00c8ff' }}>{s.angle_metrics?.elbow?.toFixed(1) ?? '--'}°</td>
                                                                <td style={{ padding: '10px 12px', color: '#ffaa00' }}>{s.angle_metrics?.knee?.toFixed(1) ?? '--'}°</td>
                                                                <td style={{ padding: '10px 12px' }}>
                                                                    {s.injury_flags.length > 0
                                                                        ? <span style={{ color: '#ff4d6d', fontWeight: 700 }}>{s.injury_flags.length} ⚠</span>
                                                                        : <span style={{ color: '#00ff88' }}>✓ Safe</span>
                                                                    }
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    )}
                                </>
                            ) : (
                                <div style={{ ...card, padding: '56px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
                                    {selectedSession.status === 'processing' ? (
                                        <>
                                            <div style={{ width: 48, height: 48, borderRadius: '50%', border: '3px solid #00ff88', borderTopColor: 'transparent', animation: 'spin 0.9s linear infinite' }} />
                                            <p style={{ fontWeight: 700, fontSize: 16, color: '#fff', margin: 0 }}>Processing {isImage ? 'Image' : 'Video'}…</p>
                                            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', margin: 0 }}>AI analysis is running in the background. The dashboard will update automatically.</p>
                                        </>
                                    ) : selectedSession.status === 'error' ? (
                                        <>
                                            <X size={40} color='#ff4d6d' />
                                            <p style={{ fontWeight: 700, fontSize: 16, color: '#ff4d6d', margin: 0 }}>Processing Failed</p>
                                            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', margin: 0 }}>Please try uploading again.</p>
                                        </>
                                    ) : (
                                        <>
                                            <Activity size={40} color='rgba(255,255,255,0.1)' />
                                            <p style={{ fontWeight: 700, fontSize: 16, color: 'rgba(255,255,255,0.4)', margin: 0 }}>No Shots Detected</p>
                                            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', margin: 0 }}>Try a different video/image with a player visible.</p>
                                        </>
                                    )}
                                </div>
                            )}
                        </>
                    ) : (
                        <WorkflowDiagram />
                    )}
                </main>
            </div>

            {/* Render Chatbot Globally */}
            <AIChatbot session={selectedSession} />

            {/* Global animation keyframes */}
            <style>{`
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
                @keyframes spin { to { transform: rotate(360deg) } }
                @keyframes pulse-bar {
                    0%, 100% { opacity: 1; transform: scaleX(1) }
                    50% { opacity: 0.7; transform: scaleX(0.85) }
                }
                * { box-sizing: border-box; }
                body { background: #080810; margin: 0; }
                ::-webkit-scrollbar { width: 6px; height: 6px; }
                ::-webkit-scrollbar-track { background: transparent; }
                ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 6px; }
            `}</style>
        </div>
    )
}
