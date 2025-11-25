import { useState, useRef, useEffect } from 'react'
import './VoicePlayer.css'

/**
 * Enhanced Voice Message Player Component
 * Features:
 * - Custom play/pause button with animation
 * - Progress bar with seek functionality
 * - Time display (current/total)
 * - Volume control
 * - Waveform visualization
 * - Smooth animations
 */
const VoicePlayer = ({ audioUrl, label = "🎤 Voice Message" }) => {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [showVolumeControl, setShowVolumeControl] = useState(false)
  
  const audioRef = useRef(null)
  const progressRef = useRef(null)
  const volumeRef = useRef(null)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const updateTime = () => setCurrentTime(audio.currentTime)
    const updateDuration = () => {
      setDuration(audio.duration)
      setIsLoading(false)
    }
    const handleEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
    }
    const handleLoadedMetadata = () => {
      setDuration(audio.duration)
      setIsLoading(false)
    }

    audio.addEventListener('timeupdate', updateTime)
    audio.addEventListener('loadedmetadata', handleLoadedMetadata)
    audio.addEventListener('durationchange', updateDuration)
    audio.addEventListener('ended', handleEnded)
    audio.addEventListener('loadstart', () => setIsLoading(true))
    audio.addEventListener('canplay', () => setIsLoading(false))

    return () => {
      audio.removeEventListener('timeupdate', updateTime)
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata)
      audio.removeEventListener('durationchange', updateDuration)
      audio.removeEventListener('ended', handleEnded)
      audio.removeEventListener('loadstart', () => setIsLoading(true))
      audio.removeEventListener('canplay', () => setIsLoading(false))
    }
  }, [audioUrl])

  const togglePlayPause = () => {
    const audio = audioRef.current
    if (!audio) return

    if (isPlaying) {
      audio.pause()
    } else {
      audio.play().catch(err => {
        console.error('Error playing audio:', err)
        setIsPlaying(false)
      })
    }
    setIsPlaying(!isPlaying)
  }

  const handleProgressClick = (e) => {
    const audio = audioRef.current
    const progressBar = progressRef.current
    if (!audio || !progressBar) return

    const rect = progressBar.getBoundingClientRect()
    const clickX = e.clientX - rect.left
    const width = rect.width
    const percentage = clickX / width
    const newTime = percentage * duration

    audio.currentTime = newTime
    setCurrentTime(newTime)
  }

  const handleVolumeChange = (e) => {
    const audio = audioRef.current
    if (!audio) return

    const newVolume = parseFloat(e.target.value)
    audio.volume = newVolume
    setVolume(newVolume)
  }

  const toggleMute = () => {
    const audio = audioRef.current
    if (!audio) return

    if (volume > 0) {
      audio.volume = 0
      setVolume(0)
    } else {
      audio.volume = 1
      setVolume(1)
    }
  }

  const formatTime = (seconds) => {
    if (!isFinite(seconds) || isNaN(seconds)) return '0:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const progressPercentage = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div className="voice-player-container">
      <div className="voice-player-header">
        <span className="voice-player-label">{label}</span>
        {isLoading && (
          <span className="voice-player-loading">
            <span className="loading-dot"></span>
            <span className="loading-dot"></span>
            <span className="loading-dot"></span>
          </span>
        )}
      </div>

      <div className="voice-player-main">
        {/* Play/Pause Button */}
        <button
          className={`voice-player-play-btn ${isPlaying ? 'playing' : ''}`}
          onClick={togglePlayPause}
          disabled={isLoading}
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" />
              <rect x="14" y="4" width="4" height="16" />
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
          )}
        </button>

        {/* Progress Bar and Time */}
        <div className="voice-player-controls">
          <div
            ref={progressRef}
            className="voice-player-progress-container"
            onClick={handleProgressClick}
          >
            <div className="voice-player-progress-track">
              <div
                className="voice-player-progress-fill"
                style={{ width: `${progressPercentage}%` }}
              >
                <div className="voice-player-progress-handle"></div>
              </div>
            </div>
          </div>

          <div className="voice-player-time">
            <span>{formatTime(currentTime)}</span>
            <span className="time-separator">/</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>

        {/* Volume Control */}
        <div className="voice-player-volume-container">
          <button
            className="voice-player-volume-btn"
            onClick={toggleMute}
            onMouseEnter={() => setShowVolumeControl(true)}
            aria-label={volume > 0 ? 'Mute' : 'Unmute'}
          >
            {volume === 0 ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
              </svg>
            ) : volume < 0.5 ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z"/>
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
              </svg>
            )}
          </button>

          {showVolumeControl && (
            <div
              className="voice-player-volume-slider-container"
              onMouseLeave={() => setShowVolumeControl(false)}
            >
              <input
                ref={volumeRef}
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={volume}
                onChange={handleVolumeChange}
                className="voice-player-volume-slider"
              />
            </div>
          )}
        </div>
      </div>

      {/* Hidden audio element */}
      <audio
        ref={audioRef}
        src={audioUrl}
        preload="metadata"
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />
    </div>
  )
}

export default VoicePlayer

