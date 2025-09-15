import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Stack,
  Box,
  Chip,
  CircularProgress,
} from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFnsV3';
import ruLocale from 'date-fns/locale/ru';
import AddPhotoAlternateIcon from '@mui/icons-material/AddPhotoAlternate';
import DeleteIcon from '@mui/icons-material/Delete';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';

import {
  uploadImageForPost,
  createPost,
  updatePost,
  deletePost,
} from '@/shared/api';

const PostEditorModal = ({ open, onClose, post, selectedDate }) => {
  const queryClient = useQueryClient();
  const [text, setText] = useState('');
  const [publishAt, setPublishAt] = useState(new Date());
  const [attachments, setAttachments] = useState([]);
  const [isUploading, setIsUploading] = useState(false);

  const isEditMode = !!post;

  useEffect(() => {
    if (open) {
      if (isEditMode) {
        setText(post.post_text || '');
        setPublishAt(new Date(post.publish_at));
        setAttachments(post.attachments || []);
      } else {
        setText('');
        setPublishAt(selectedDate ? new Date(selectedDate) : new Date());
        setAttachments([]);
      }
    }
  }, [open, post, selectedDate, isEditMode]);

  const createMutation = useMutation({
    mutationFn: createPost,
    onSuccess: () => {
      toast.success('Пост успешно запланирован!');
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      onClose();
    },
    onError: () => toast.error('Ошибка планирования поста'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ postId, data }) => updatePost(postId, data),
    onSuccess: () => {
      toast.success('Пост успешно обновлен!');
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      onClose();
    },
    onError: () => toast.error('Ошибка обновления поста'),
  });

  const deleteMutation = useMutation({
    mutationFn: deletePost,
    onSuccess: () => {
      toast.success('Пост удален.');
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      onClose();
    },
    onError: () => toast.error('Ошибка удаления'),
  });

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setIsUploading(true);
    const formData = new FormData();
    formData.append('image', file);
    try {
      const res = await uploadImageForPost(formData);
      setAttachments((prev) => [...prev, res.attachment_id]);
    } catch (error) {
      toast.error('Ошибка загрузки изображения');
    } finally {
      setIsUploading(false);
      e.target.value = null;
    }
  };

  const handleSave = () => {
    const postData = {
      post_text: text,
      publish_at: publishAt.toISOString(),
      attachments,
    };
    if (isEditMode) {
      updateMutation.mutate({ postId: post.id, data: postData });
    } else {
      createMutation.mutate(postData);
    }
  };

  const handleDelete = () => {
    if (window.confirm('Вы уверены, что хотите удалить этот пост?')) {
      deleteMutation.mutate(post.id);
    }
  };

  const isLoading =
    createMutation.isLoading ||
    updateMutation.isLoading ||
    deleteMutation.isLoading;

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        {isEditMode ? 'Редактировать пост' : 'Новый пост'}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={3} sx={{ pt: 1 }}>
          <TextField
            multiline
            rows={8}
            label="Текст поста"
            value={text}
            onChange={(e) => setText(e.target.value)}
            fullWidth
          />
          <Box>
            <Button
              component="label"
              startIcon={
                isUploading ? (
                  <CircularProgress size={20} />
                ) : (
                  <AddPhotoAlternateIcon />
                )
              }
              disabled={isUploading}
            >
              Загрузить фото
              <input
                type="file"
                hidden
                accept="image/*"
                onChange={handleImageUpload}
              />
            </Button>
            <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap">
              {attachments.map((att) => (
                <Chip
                  key={att}
                  label="Фото"
                  onDelete={() =>
                    setAttachments((prev) => prev.filter((a) => a !== att))
                  }
                />
              ))}
            </Stack>
          </Box>
          <LocalizationProvider
            dateAdapter={AdapterDateFns}
            adapterLocale={ruLocale}
          >
            <DateTimePicker
              label="Дата и время публикации"
              value={publishAt}
              onChange={setPublishAt}
              renderInput={(params) => <TextField {...params} />}
            />
          </LocalizationProvider>
        </Stack>
      </DialogContent>
      <DialogActions sx={{ justifyContent: 'space-between', p: 2 }}>
        <Box>
          {isEditMode && (
            <Button
              color="error"
              startIcon={<DeleteIcon />}
              onClick={handleDelete}
              disabled={isLoading}
            >
              Удалить
            </Button>
          )}
        </Box>
        <Box>
          <Button onClick={onClose} disabled={isLoading}>
            Отмена
          </Button>
          <Button onClick={handleSave} variant="contained" disabled={isLoading}>
            {isLoading ? <CircularProgress size={24} /> : 'Сохранить'}
          </Button>
        </Box>
      </DialogActions>
    </Dialog>
  );
};

export default PostEditorModal;
