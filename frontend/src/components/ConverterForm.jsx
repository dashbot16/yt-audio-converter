import React, { useState } from 'react';
import axios from 'axios';

const formats = ["mp3", "wav", "aac", "ogg", "flac", "m4a", "wma", "opus", "alac"];
const bitrates = ["128k", "192k", "256k", "320k"];

const ConverterForm = () => {
  const [url, setUrl] = useState('');
  const [format, setFormat] = useState('mp3');
  const [bitrate, setBitrate] = useState('192k');
  const [normalize, setNormalize] = useState(false);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [jobId, setJobId] = useState('');
  const [filename, setFilename] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [title, setTitle] = useState('');


  const reset = () => {
    setLoading(false);
    setStatusMsg('');
    setJobId('');
    setFilename('');
    setErrorMsg('');
  };

  const handleConvert = async () => {
    if (!url) return alert('Please enter a YouTube URL');

    reset();
    setLoading(true);
    setStatusMsg('🚀 Requesting conversion...');

    try {
      const { data } = await axios.post('http://localhost:5000/convert', { url, format });
      const job = data.job_id;
      setJobId(job);

      const interval = setInterval(async () => {
        const res = await axios.get(`http://localhost:5000/status/${job}`);
        const status = res.data.status;
        setStatusMsg(`⏳ Status: ${status}`);

        if (status === 'ready') {
          clearInterval(interval);
          setLoading(false);
          setFilename(res.data.filename);
          setTitle(res.data.title); // Add this line
          setStatusMsg('✅ Ready! Downloading...');
          setTimeout(() => {
            window.location.href = `http://localhost:5000/download/${job}`;
          }, 1000);
        }
        

        if (status === 'error') {
          clearInterval(interval);
          setLoading(false);
          setErrorMsg(res.data.error || 'An error occurred');
          setStatusMsg('❌ Conversion failed.');
        }
      }, 2000);
    } catch (err) {
      console.error('🔥 Frontend error:', err);
      setErrorMsg('Something went wrong while requesting conversion.');
      setLoading(false);
    }
  };

  return (
    <div className="form">
      <input
        type="text"
        placeholder="Paste YouTube URL here..."
        value={url}
        onChange={(e) => setUrl(e.target.value)}
      />

      <div className="options">
        <label>Format:</label>
        <select value={format} onChange={(e) => setFormat(e.target.value)}>
          {formats.map(fmt => (
            <option key={fmt} value={fmt}>{fmt.toUpperCase()}</option>
          ))}
        </select>

        <label>Bitrate:</label>
        <select value={bitrate} onChange={(e) => setBitrate(e.target.value)}>
          {bitrates.map(rate => (
            <option key={rate} value={rate}>{rate}</option>
          ))}
        </select>

        <label>
          <input
            type="checkbox"
            checked={normalize}
            onChange={() => setNormalize(!normalize)}
          />
          Normalize Audio
        </label>
      </div>

      <div>
      <br/>
      </div>

      <button onClick={handleConvert} disabled={loading}>
        {loading ? 'Processing...' : 'Convert & Download'}
      </button>

      {title && <p className="video-title">🎬 Title: <strong>{title}</strong></p>}
      {filename && <p className="filename">📁 File: <strong>{filename}</strong></p>}
      {loading && <div className="spinner"></div>}
      {statusMsg && <p className="status">{statusMsg}</p>}
      {errorMsg && (
        <div className="error">
          <p>{errorMsg}</p>
          <button onClick={handleConvert}>🔁 Retry</button>
        </div>
      )}
    </div>
  );
};

export default ConverterForm;
