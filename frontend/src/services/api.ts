/**
 * API客户端
 */
import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: `${API_BASE_URL}/api/v1`,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // 请求拦截器
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Token过期，清除并跳转登录
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // 认证API
  async register(data: { username: string; email: string; password: string }) {
    const response = await this.client.post('/auth/register', data);
    return response.data;
  }

  async login(data: { email: string; password: string }) {
    const response = await this.client.post('/auth/login', data);
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
    }
    return response.data;
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  // 教学模型API
  async getTeachingModels() {
    const response = await this.client.get('/teaching-models');
    return response.data;
  }

  async getTeachingModel(id: string) {
    const response = await this.client.get(`/teaching-models/${id}`);
    return response.data;
  }

  // 教案API
  async createLesson(data: FormData) {
    const response = await this.client.post('/lessons', data, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async getLessons(params?: { status?: string; limit?: number; offset?: number }) {
    const response = await this.client.get('/lessons', { params });
    return response.data;
  }

  async getLesson(id: string) {
    const response = await this.client.get(`/lessons/${id}`);
    return response.data;
  }

  async deleteLesson(id: string) {
    await this.client.delete(`/lessons/${id}`);
  }

  // 导出API
  async exportWord(lessonId: string) {
    const response = await this.client.get(`/export/word/${lessonId}`);
    return response.data;
  }

  async exportPDF(lessonId: string) {
    const response = await this.client.get(`/export/pdf/${lessonId}`);
    return response.data;
  }

  async exportTXT(lessonId: string, clean: boolean = true) {
    const response = await this.client.get(`/export/txt/${lessonId}`, {
      params: { clean },
    });
    return response.data;
  }

  async exportJSON(lessonId: string) {
    const response = await this.client.get(`/export/json/${lessonId}`);
    return response.data;
  }

  async exportAll(lessonId: string) {
    const response = await this.client.get(`/export/all/${lessonId}`);
    return response.data;
  }
}

export const apiClient = new APIClient();

