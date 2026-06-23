import { useState } from 'react';
import { Search, Loader2, Download, Play, Video } from 'lucide-react';
import api from '@/api';

interface VideoFormat {
  format_id: string;
  resolution: string;
  ext: string;
  filesize: number | null;
}

interface VideoInfo {
  title: string;
  thumbnail: string;
  formats: VideoFormat[];
}

export function Home() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);

  const fetchVideoInfo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setLoading(true);
    setError('');
    setVideoInfo(null);

    try {
      const res = await api.get('/video/info', {
        params: { url }
      });
      setVideoInfo(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch video information');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (formatId: string) => {
    try {
      // 1. Get short-lived download token
      const tokenRes = await api.get('/video/download-token');
      const downloadToken = tokenRes.data.download_token;

      // 2. Construct download URL with token
      const downloadUrl = `${api.defaults.baseURL}/video/download?token=${downloadToken}&url=${encodeURIComponent(url)}&format_id=${encodeURIComponent(formatId)}`;

      // 3. Trigger download via hidden iframe or window location
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.setAttribute('download', ''); // hint browser to download
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

    } catch (err: any) {
      setError('Failed to initiate download: ' + (err.response?.data?.detail || 'Unknown error'));
    }
  };

  const formatFileSize = (bytes: number | null) => {
    if (!bytes) return 'Unknown size';
    const mb = bytes / (1024 * 1024);
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    return `${(mb / 1024).toFixed(2)} GB`;
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-extrabold text-gray-900 sm:text-5xl flex items-center justify-center gap-3">
          <Video className="h-12 w-12 text-blue-600" />
          Private Downloader
        </h1>
        <p className="mt-4 text-xl text-gray-500">
          Enter a video URL to get started. Secure, fast, and no disk I/O.
        </p>
      </div>

      <div className="bg-white shadow-xl rounded-2xl p-6 sm:p-8 border border-gray-100">
        <form onSubmit={fetchVideoInfo} className="relative">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-grow">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-gray-400" />
              </div>
              <input
                type="url"
                required
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="block w-full pl-11 pr-4 py-4 border-2 border-gray-200 rounded-xl leading-5 bg-gray-50 placeholder-gray-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 sm:text-lg transition-colors"
                placeholder="https://www.youtube.com/watch?v=..."
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center justify-center px-8 py-4 border border-transparent text-lg font-medium rounded-xl text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-70 transition-colors shadow-md"
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin -ml-1 mr-2 h-5 w-5" />
                  Analyzing...
                </>
              ) : (
                'Search'
              )}
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-6 bg-red-50 border-l-4 border-red-500 p-4 rounded-md">
            <div className="flex">
              <div className="ml-3">
                <p className="text-sm text-red-700 font-medium">{error}</p>
              </div>
            </div>
          </div>
        )}

        {videoInfo && (
          <div className="mt-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col md:flex-row gap-8">
              <div className="w-full md:w-1/3 shrink-0">
                <div className="rounded-xl overflow-hidden shadow-lg border border-gray-100 relative group">
                  <img
                    src={videoInfo.thumbnail}
                    alt={videoInfo.title}
                    className="w-full h-auto object-cover aspect-video bg-gray-100"
                  />
                  <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <Play className="text-white w-12 h-12 fill-white/80" />
                  </div>
                </div>
              </div>
              <div className="flex-grow flex flex-col">
                <h3 className="text-2xl font-bold text-gray-900 mb-6 leading-tight line-clamp-2" title={videoInfo.title}>
                  {videoInfo.title}
                </h3>

                <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden flex-grow">
                  <div className="px-4 py-3 bg-gray-100 border-b border-gray-200">
                    <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">Available Formats</h4>
                  </div>
                  <ul className="divide-y divide-gray-200 max-h-80 overflow-y-auto">
                    {videoInfo.formats.map((format, idx) => (
                      <li key={`${format.format_id}-${idx}`} className="px-4 py-4 hover:bg-gray-100/50 transition-colors flex items-center justify-between gap-4">
                        <div className="flex flex-col">
                          <span className="text-sm font-bold text-gray-900">
                            {format.resolution === 'audio only' ? 'Audio Only' : format.resolution}
                          </span>
                          <span className="text-xs text-gray-500 flex items-center gap-1.5 mt-1">
                            <span className="uppercase font-medium bg-gray-200 px-1.5 py-0.5 rounded text-gray-600">{format.ext}</span>
                            <span>•</span>
                            <span>{formatFileSize(format.filesize)}</span>
                          </span>
                        </div>
                        <button
                          onClick={() => handleDownload(format.format_id)}
                          className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-lg text-blue-700 bg-white hover:bg-blue-50 hover:border-blue-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all"
                        >
                          <Download className="h-4 w-4 mr-2" />
                          Download
                        </button>
                      </li>
                    ))}
                    {videoInfo.formats.length === 0 && (
                      <li className="px-4 py-8 text-center text-gray-500 text-sm">
                        No downloadable formats found.
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}