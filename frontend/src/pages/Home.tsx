import { useState } from 'react';
import { Search, Loader2, Download, Play, Video } from 'lucide-react';
import api from '@/api';

interface VideoFormat {
  format_id: string;
  resolution: string;
  ext: string;
  filesize: number | null;
  description?: string;
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
  const [activeJob, setActiveJob] = useState<{ id: string, status: string, progress: number, message: string } | null>(null);

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
      if (err.response?.data?.detail === 'COOKIE_ERROR') {
        setError('유튜브 봇 감지에 의해 차단되었습니다. Google 재로그인을 시도하거나, 설정에서 쿠키를 추가해주세요.');
        window.dispatchEvent(new Event('open-cookie-modal'));
      } else {
        setError(err.response?.data?.detail || 'Failed to fetch video information');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (formatId: string) => {
    try {
      const tokenRes = await api.get('/video/download-token');
      const downloadToken = tokenRes.data.download_token;

      const res = await api.post('/video/prepare-download', null, {
        params: {
          token: downloadToken,
          url: url,
          format_id: formatId
        }
      });
      
      const jobId = res.data.job_id;
      setActiveJob({ id: jobId, status: 'starting', progress: 0, message: '서버 다운로드 준비 중...' });
      pollJobStatus(jobId, downloadToken);
    } catch (err: any) {
      setError('Failed to initiate download: ' + (err.response?.data?.detail || 'Unknown error'));
    }
  };

  const pollJobStatus = async (jobId: string, token: string) => {
    try {
      const res = await api.get(`/video/status/${jobId}`);
      setActiveJob(res.data);

      if (res.data.status === 'error') {
        if (res.data.message === 'COOKIE_ERROR') {
          setError('유튜브 봇 감지에 의해 다운로드가 실패했습니다. Google 재로그인을 시도하거나 설정에서 쿠키를 추가해주세요.');
          window.dispatchEvent(new Event('open-cookie-modal'));
        } else {
          setError(res.data.message);
        }
        setTimeout(() => setActiveJob(null), 3000);
        return;
      }

      if (res.data.status === 'ready') {
        // Trigger actual download
        const downloadUrl = `${api.defaults.baseURL}/video/download-file/${jobId}?token=${token}`;
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.setAttribute('download', '');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        setTimeout(() => setActiveJob(null), 3000);
        return;
      }

      // Poll again after 1 second
      setTimeout(() => pollJobStatus(jobId, token), 1000);
    } catch (err) {
      setTimeout(() => pollJobStatus(jobId, token), 1000);
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
                          {format.description && (
                            <span className="text-xs text-gray-400 mt-1">
                              {format.description}
                            </span>
                          )}
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

      {activeJob && (
        <div className="fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center z-50 px-4">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl">
            <h3 className="text-xl font-bold text-gray-900 mb-4">다운로드 진행 상황</h3>
            <p className="text-gray-600 mb-6 text-sm">{activeJob.message}</p>
            
            <div className="w-full bg-gray-200 rounded-full h-3 mb-2 overflow-hidden">
              <div 
                className={`h-3 rounded-full transition-all duration-300 ${activeJob.status === 'error' ? 'bg-red-500' : activeJob.status === 'ready' ? 'bg-green-500' : 'bg-blue-600'}`}
                style={{ width: `${Math.max(5, activeJob.progress)}%` }}
              ></div>
            </div>
            
            <div className="flex justify-between text-xs text-gray-500 font-medium">
              <span>{activeJob.status === 'merging' ? '병합 중...' : activeJob.status === 'ready' ? '완료' : '진행 중'}</span>
              <span>{activeJob.progress.toFixed(1)}%</span>
            </div>
            
            {activeJob.status === 'ready' && (
              <p className="text-green-600 text-sm mt-6 font-bold text-center">다운로드가 시작되었습니다!</p>
            )}
            {activeJob.status === 'error' && (
              <button onClick={() => setActiveJob(null)} className="mt-6 w-full py-2 bg-gray-100 text-gray-800 rounded-lg font-medium hover:bg-gray-200">닫기</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}