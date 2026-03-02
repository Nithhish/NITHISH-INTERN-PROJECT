import { useState, useEffect } from 'react'
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
    LineChart, Line, AreaChart, Area
} from 'recharts'
import {
    Upload, User, Activity, AlertTriangle, ChevronRight,
    Trophy, TrendingUp, Clock, Target, Play
} from 'lucide-react'
import axios from 'axios'

const API_BASE = '/api'

export default function App() {
    const [player, setPlayer] = useState(null)
    const [sessions, setSessions] = useState([])
    const [selectedSession, setSelectedSession] = useState(null)
    const [isUploading, setIsUploading] = useState(false)
    const [uploadProgress, setUploadProgress] = useState(0)

    // Demo fallback data in case DB is empty initially
    const demoData = {
        radar: [
            { subject: 'Speed', A: 85, fullMark: 100 },
            { subject: 'Stability', A: 92, fullMark: 100 },
            { subject: 'Timing', A: 78, fullMark: 100 },
            { subject: 'Accuracy', A: 88, fullMark: 100 },
            { subject: 'Power', A: 70, fullMark: 100 },
        ],
        angles: [
            { name: 'Impact 1', elbow: 155, knee: 135 },
            { name: 'Impact 2', elbow: 162, knee: 142 },
            { name: 'Impact 3', elbow: 158, knee: 138 },
            { name: 'Impact 4', elbow: 160, knee: 140 },
        ]
    }

    useEffect(() => {
        // Auto-create or fetch a demo player for development
        const initApp = async () => {
            try {
                const res = await axios.get(`${API_BASE}/players/`)
                if (res.data.length > 0) {
                    setPlayer(res.data[0])
                } else {
                    // Create default player
                    const newPlayer = await axios.post(`${API_BASE}/players/`, {
                        name: "Pro Cricketer",
                        email: "pro@cricket.ai"
                    })
                    setPlayer(newPlayer.data)
                }
            } catch (err) {
                console.error("Failed to init app", err)
            }
        }
        initApp()
    }, [])

    const handleFileUpload = async (e) => {
        const file = e.target.files[0]
        if (!file || !player) return

        setIsUploading(true)
        const formData = new FormData()
        formData.append('file', file)

        try {
            const res = await axios.post(`${API_BASE}/upload/${player.id}`, formData)
            alert("Processing started! ID: " + res.data.session_id)
            // Poll for results...
        } catch (err) {
            alert("Upload failed")
        } finally {
            setIsUploading(false)
        }
    }

    return (
        <div className="min-h-screen p-6 lg:p-10 max-w-[1600px] mx-auto">
            {/* Header */}
            <header className="flex justify-between items-center mb-10">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight mb-1">Cricket<span className="text-cricket-green">AI</span> Analysis</h1>
                    <p className="text-white/50">Level up your technique with biomechanical feedback</p>
                </div>

                <div className="flex items-center gap-4 bg-white/5 p-2 pr-4 rounded-full border border-white/10">
                    <div className="w-10 h-10 bg-cricket-green rounded-full flex items-center justify-center text-black font-bold">
                        {player?.name?.[0] || <User size={20} />}
                    </div>
                    <span className="font-medium">{player?.name || "Guest Player"}</span>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Sidebar / List */}
                <aside className="lg:col-span-3 flex flex-col gap-6">
                    {/* Upload Card */}
                    <div className="glass-card p-6 border-cricket-green/20">
                        <h3 className="font-semibold mb-4 flex items-center gap-2">
                            <Upload size={18} className="text-cricket-green" /> New Session
                        </h3>
                        <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-white/10 rounded-xl cursor-pointer hover:border-cricket-green/50 transition-colors">
                            <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                <Play size={24} className="mb-2 text-white/40" />
                                <p className="text-sm text-white/40">Upload Video</p>
                            </div>
                            <input type="file" className="hidden" accept="video/*" onChange={handleFileUpload} disabled={isUploading} />
                        </label>
                        {isUploading && (
                            <div className="mt-4 text-xs text-cricket-green animate-pulse">
                                Uploading and processing...
                            </div>
                        )}
                    </div>

                    {/* Recent Sessions */}
                    <div className="glass-card p-6 flex-grow">
                        <h3 className="font-semibold mb-4 flex items-center gap-2">
                            <Clock size={18} className="text-white/60" /> Sessions
                        </h3>
                        <div className="space-y-3">
                            {[1, 2, 3].map(i => (
                                <div key={i} className="p-3 rounded-lg bg-white/5 border border-white/5 hover:bg-white/10 cursor-pointer flex justify-between items-center group">
                                    <div>
                                        <p className="text-sm font-medium">Session #{1000 + i}</p>
                                        <p className="text-[10px] text-white/40">March 0{i}, 2026</p>
                                    </div>
                                    <ChevronRight size={16} className="text-white/20 group-hover:text-cricket-green transition-colors" />
                                </div>
                            ))}
                        </div>
                    </div>
                </aside>

                {/* Main Analytics Area */}
                <main className="lg:col-span-9 space-y-6">
                    {/* Top Score Summary */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="glass-card p-6 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                                <Trophy size={80} />
                            </div>
                            <h4 className="text-white/50 text-xs font-semibold uppercase tracking-wider mb-2">Overall Tech Score</h4>
                            <div className="flex items-end gap-2">
                                <span className="text-5xl font-black text-white">82.4</span>
                                <span className="text-cricket-green text-sm font-bold mb-2">+4.2%</span>
                            </div>
                            <div className="mt-4 h-1 bg-white/10 rounded-full overflow-hidden">
                                <div className="h-full bg-cricket-green w-[82.4%]" />
                            </div>
                        </div>

                        <div className="glass-card p-6">
                            <h4 className="text-white/50 text-xs font-semibold uppercase tracking-wider mb-2">Stability Stability</h4>
                            <div className="flex items-end gap-2">
                                <span className="text-5xl font-black text-white">0.024</span>
                                <span className="text-cricket-green text-sm font-bold mb-2">Stable</span>
                            </div>
                            <p className="text-[10px] text-white/40 mt-4 leading-relaxed">Lower is better. You are currently in the top 5% of stable hitters.</p>
                        </div>

                        <div className="glass-card p-6 border-red-500/20">
                            <h4 className="flex items-center gap-2 text-red-400 text-xs font-semibold uppercase tracking-wider mb-2">
                                <AlertTriangle size={14} /> Injury Risks
                            </h4>
                            <div className="flex items-end gap-2">
                                <span className="text-5xl font-black text-white">1</span>
                                <span className="text-red-400 text-sm font-bold mb-2">Flagged</span>
                            </div>
                            <p className="text-[10px] text-red-300 mt-4">Lumbar over-extension detected in session #1003. Review back posture.</p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Angle Consistency Chart */}
                        <div className="glass-card p-6">
                            <h3 className="font-semibold mb-6 flex items-center gap-2">
                                <Activity size={18} className="text-cricket-green" /> Impact Angle Consistency
                            </h3>
                            <div className="h-64 cursor-default">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={demoData.angles}>
                                        <defs>
                                            <linearGradient id="colorElbow" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#00ff88" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#00ff88" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#222" />
                                        <XAxis dataKey="name" stroke="#555" fontSize={10} />
                                        <YAxis stroke="#555" fontSize={10} domain={[120, 180]} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#121216', border: '1px solid #333', borderRadius: '8px' }}
                                            itemStyle={{ fontSize: '12px' }}
                                        />
                                        <Area type="monotone" dataKey="elbow" stroke="#00ff88" fillOpacity={1} fill="url(#colorElbow)" strokeWidth={3} />
                                        <Area type="monotone" dataKey="knee" stroke="#ffaa00" fill="transparent" strokeWidth={2} strokeDasharray="5 5" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                            <div className="mt-4 flex gap-6 text-[10px] uppercase font-bold tracking-widest justify-center">
                                <div className="flex items-center gap-2"><div className="w-3 h-1 bg-cricket-green rounded-full" /> Elbow Angle</div>
                                <div className="flex items-center gap-2"><div className="w-3 h-1 bg-cricket-orange border-dashed border-t rounded-full" /> Knee Angle</div>
                            </div>
                        </div>

                        {/* Radar Skill Chart */}
                        <div className="glass-card p-6">
                            <h3 className="font-semibold mb-6 flex items-center gap-2">
                                <Target size={18} className="text-cricket-orange" /> Skill Matrix
                            </h3>
                            <div className="h-64 cursor-default">
                                <ResponsiveContainer width="100%" height="100%">
                                    <RadarChart cx="50%" cy="50%" outerRadius="80%" data={demoData.radar}>
                                        <PolarGrid stroke="#222" />
                                        <PolarAngleAxis dataKey="subject" stroke="#888" fontSize={10} />
                                        <PolarRadiusAxis angle={30} domain={[0, 100]} axisLine={false} tick={false} />
                                        <Radar
                                            name="Player"
                                            dataKey="A"
                                            stroke="#ffaa00"
                                            fill="#ffaa00"
                                            fillOpacity={0.4}
                                        />
                                    </RadarChart>
                                </ResponsiveContainer>
                            </div>
                            <div className="mt-4 text-center">
                                <button className="text-[10px] text-cricket-green font-bold uppercase tracking-widest border border-cricket-green/30 px-4 py-2 rounded-full hover:bg-cricket-green/10 transition-colors">
                                    Generate PDF Report
                                </button>
                            </div>
                        </div>
                    </div>
                </main>
            </div>
        </div>
    )
}
