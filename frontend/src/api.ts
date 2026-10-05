import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api', // Use env var if available, else fallback to proxy
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401 redirect removed to disable login requirement
    return Promise.reject(error);
  }
);

export const getProjects = () => api.get('/projects');
export const getProject = (id: string) => api.get(`/projects/${id}`);
export const createProject = (data: { name: string, description?: string }) => api.post('/projects', data);
export const updateProject = (id: string, data: { name?: string, description?: string, own_business_id?: string }) => api.patch(`/projects/${id}`, data);
export const getProjectSummary = (id: string) => api.get(`/projects/${id}/summary`);

export interface BusinessProfile {
  id: string;
  business_name: string;
  google_maps_url?: string;
  canonical_source_id?: string;
  address?: string;
  category?: string;
}

export interface Competitor {
  id: string;
  project_id: string;
  business_id: string;
  is_active: boolean;
  business?: BusinessProfile;
}

export interface DirectCompetitorCreate {
  source_identifier?: string;
  source_url?: string;
  business_name: string;
  category?: string;
  address?: string;
  locality?: string;
  latitude?: number;
  longitude?: number;
  rating?: number;
  review_count?: number;
  phone?: number;
  website?: string;
}

export interface DiscoveryRun {
  id: string;
  project_id: string;
  query?: string;
  location?: string;
  latitude?: number;
  longitude?: number;
  radius?: number;
  category?: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  total_candidates: number;
  duplicates_skipped: number;
  error_message?: string;
}

export interface DiscoveryCandidate {
  id: string;
  discovery_run_id: string;
  source_identifier?: string;
  source_url?: string;
  business_name: string;
  category?: string;
  address?: string;
  locality?: string;
  latitude?: number;
  longitude?: number;
  rating?: number;
  review_count?: number;
  phone?: string;
  website?: string;
  status: string;
  relevance_score?: number;
}

export const getProjectCompetitors = (projectId: string) => api.get<Competitor[]>(`/projects/${projectId}/competitors`);
export const addDirectCompetitor = (projectId: string, data: DirectCompetitorCreate) => api.post<Competitor>(`/projects/${projectId}/competitors/direct`, data);

export const startDiscovery = (projectId: string, data: Record<string, string | number | boolean | undefined>) => api.post<DiscoveryRun>(`/projects/${projectId}/discovery`, data);
export const getDiscoveryRuns = (projectId: string) => api.get<DiscoveryRun[]>(`/projects/${projectId}/discovery-runs`);
export const getDiscoveryRun = (projectId: string, runId: string) => api.get<DiscoveryRun>(`/projects/${projectId}/discovery-runs/${runId}`);
export const getDiscoveryCandidates = (projectId: string, skip = 0, limit = 50) => api.get<DiscoveryCandidate[]>(`/projects/${projectId}/discovery-candidates`, { params: { skip, limit } });
export const selectDiscoveryCandidate = (projectId: string, candidateId: string) => api.post<Competitor>(`/projects/${projectId}/discovery-candidates/${candidateId}/select`);
export const rejectDiscoveryCandidate = (projectId: string, candidateId: string) => api.post<DiscoveryCandidate>(`/projects/${projectId}/discovery-candidates/${candidateId}/reject`);

export interface ScrapeRunCompetitor {
  id: string;
  business_id: string;
  business?: BusinessProfile;
  status: string;
  posts_discovered: number;
  new_posts: number;
  duplicates_skipped: number;
  error_message?: string;
}

export interface ScrapeRun {
  id: string;
  project_id: string;
  start_time?: string;
  end_time?: string;
  status: string;
  competitors_attempted: number;
  competitors_succeeded: number;
  competitors_failed: number;
  competitor_runs?: ScrapeRunCompetitor[];
}

export const startScrape = (projectId: string) => api.post<ScrapeRun>(`/projects/${projectId}/scrape`);
export const getScrapeRuns = (projectId: string) => api.get<ScrapeRun[]>(`/projects/${projectId}/scrape-runs`);
export const getScrapeRun = (runId: string) => api.get<ScrapeRun>(`/scrape-runs/${runId}`);
export const resumeScrapeRun = (runId: string) => api.post<ScrapeRun>(`/scrape-runs/${runId}/resume`);
export const deleteScrapeRun = (projectId: string, runId: string) => api.delete(`/projects/${projectId}/scrape-runs/${runId}`);





// Posts and Analytics

export interface AIAnalysisResult {
  topic?: string;
  subtopic?: string;
  keywords: string[];
  content_type?: string;
  cta_type?: string;
  offer_or_promotion?: string;
  sentiment?: string;
  summary?: string;
  confidence?: number;
}

export interface PostMediaResponse {
  id: string;
  media_url?: string;
  media_type?: string;
  mime_type?: string;
  width?: number;
  height?: number;
  file_size?: number;
}

export interface BusinessInfoResponse {
  id: string;
  business_name: string;
}

export interface PostResponse {
  id: string;
  business_id: string;
  business: BusinessInfoResponse;
  source_url?: string;
  text_content?: string;
  published_date?: string;
  scraped_date: string;
  analysis?: AIAnalysisResult;
  media: PostMediaResponse[];
}

export interface PostListResponse {
  items: PostResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export const getProjectPosts = (projectId: string, params?: Record<string, string | number | boolean | undefined>) => api.get<PostListResponse>(`/projects/${projectId}/posts`, { params });
export const getProjectPost = (projectId: string, postId: string) => api.get<PostResponse>(`/projects/${projectId}/posts/${postId}`);

export interface TopicFrequency {
  topic: string;
  count: number;
  percentage?: number;
}

export interface CompetitorTopicCoverage {
  topic: string;
  competitor_count: number;
}

export interface KeywordFrequency {
  keyword: string;
  count: number;
}

export interface ContentGaps {
  topic_gaps: string[];
  keyword_gaps: string[];
}

export interface DetailedTopicGap {
  topic: string;
  competitor_frequency: number;
  project_frequency: number;
  gap_score: number;
}

export interface DetailedKeywordGap {
  keyword: string;
  competitor_frequency: number;
  project_frequency: number;
  gap_score: number;
}

export interface DetailedContentTypeGap {
  content_type: string;
  competitor_frequency: number;
  project_frequency: number;
  gap_score: number;
}

export interface AnalyticsSummaryResponse {
  topics: TopicFrequency[];
  competitor_coverage: CompetitorTopicCoverage[];
  keywords: KeywordFrequency[];
  publishing_patterns: {
    posts_per_competitor: Record<string, unknown>[];
  };
  content_gaps: ContentGaps;
  detailed_topic_gaps: DetailedTopicGap[];
  detailed_keyword_gaps: DetailedKeywordGap[];
  detailed_content_type_gaps: DetailedContentTypeGap[];
}

export const getAnalyticsSummary = (projectId: string) => api.get<AnalyticsSummaryResponse>(`/projects/${projectId}/analytics/summary`);

// Generation

export interface GenerationRequest {
  generation_type: 'IDEA' | 'FULL';
  count?: number;
  topic?: string;
  content_type?: string;
  keywords?: string[];
  cta_style?: string;
  campaign_context?: string;
}

export interface RegenerateRequest {
  regeneration_reason?: string;
}

export interface GeneratedContentResponse {
  id: string;
  project_id: string;
  generation_type: 'IDEA' | 'FULL';
  topic?: string;
  generated_idea?: string;
  full_copy?: string;
  keywords?: string[];
  cta?: string;
  image_concept?: string;
  content_type?: string;
  provider?: string;
  model_name?: string;
  prompt_version?: string;
  status: 'QUEUED' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'REJECTED_DUPLICATE';
  error_message?: string;
  created_at: string;
  updated_at: string;
  parent_generation_id?: string;
  regeneration_reason?: string;
}

export const startGeneration = (projectId: string, data: GenerationRequest) => api.post<GeneratedContentResponse[]>(`/projects/${projectId}/content/generate`, data);
export const regenerateContent = (projectId: string, contentId: string, data: RegenerateRequest) => api.post<GeneratedContentResponse>(`/projects/${projectId}/content/${contentId}/regenerate`, data);
export const getGenerations = (projectId: string, skip = 0, limit = 50) => api.get<GeneratedContentResponse[]>(`/projects/${projectId}/content`, { params: { skip, limit } });
export const getGeneration = (projectId: string, contentId: string) => api.get<GeneratedContentResponse>(`/projects/${projectId}/content/${contentId}`);

export default api;
