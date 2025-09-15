import { apiClient } from './index';

export const fetchPosts = () =>
  apiClient.get('/api/v1/posts').then((res) => res.data);

export const createPost = (data) =>
  apiClient.post('/api/v1/posts', data).then((res) => res.data);

export const updatePost = (id, data) =>
  apiClient.put(`/api/v1/posts/${id}`, data).then((res) => res.data);

export const deletePost = (id) => apiClient.delete(`/api/v1/posts/${id}`);

export const uploadImageForPost = (formData) =>
  apiClient
    .post('/api/v1/posts/upload-image', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    .then((res) => res.data);
