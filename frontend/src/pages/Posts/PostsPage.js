import React, { useState, useMemo } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  useTheme,
} from '@mui/material';
import { styled, alpha } from '@mui/material/styles';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';

import { fetchPosts, updatePost } from '@/shared/api/api';
import PostEditorModal from './PostEditorModal';

const StyledCalendarWrapper = styled(Box)(({ theme }) => ({
  '& .fc': {
    '--fc-border-color': theme.palette.divider,
    '--fc-daygrid-event-dot-width': '8px',
    '--fc-event-border-color': 'transparent',
    '--fc-event-text-color': theme.palette.common.white,
    '--fc-today-bg-color': alpha(theme.palette.primary.main, 0.1),
    '--fc-page-bg-color': 'transparent',
    '--fc-neutral-bg-color': 'transparent',
  },
  '& .fc .fc-toolbar-title': {
    fontSize: '1.5em',
    fontWeight: 700,
    color: theme.palette.text.primary,
  },
  '& .fc .fc-button': {
    background: alpha(theme.palette.text.secondary, 0.1),
    color: theme.palette.text.primary,
    border: `1px solid ${theme.palette.divider}`,
    textTransform: 'none',
    boxShadow: 'none',
    '&:hover': { background: alpha(theme.palette.text.secondary, 0.2) },
  },
  '& .fc .fc-button-primary:not(:disabled).fc-button-active, .fc .fc-button-primary:not(:disabled):active':
    {
      backgroundColor: theme.palette.primary.main,
      borderColor: theme.palette.primary.main,
    },
  '& .fc-daygrid-day.fc-day-today': {
    background: alpha(theme.palette.primary.dark, 0.15),
  },
  '& .fc-event': {
    padding: '4px 8px',
    borderRadius: theme.shape.borderRadius,
    cursor: 'pointer',
    transition: 'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out',
    border: 'none !important',
    '&:hover': {
      transform: 'translateY(-2px)',
      boxShadow: theme.shadows[4],
    },
  },
  '& .fc-daygrid-day-number': {
    color: theme.palette.text.secondary,
    padding: '8px',
  },
}));

const PostsPage = () => {
  const theme = useTheme();
  const queryClient = useQueryClient();
  const [modalState, setModalState] = useState({
    open: false,
    event: null,
    date: null,
  });

  const { data: posts, isLoading } = useQuery({
    queryKey: ['posts'],
    queryFn: fetchPosts,
  });

  const updateMutation = useMutation({
    mutationFn: ({ postId, data }) => updatePost(postId, data),
    onSuccess: () => {
      toast.success('Дата публикации обновлена');
      queryClient.invalidateQueries({ queryKey: ['posts'] });
    },
    onError: () => toast.error('Не удалось обновить дату'),
  });

  const events = useMemo(
    () =>
      posts?.map((post) => ({
        id: post.id.toString(),
        title: post.post_text,
        start: new Date(post.publish_at),
        allDay: false,
        backgroundColor: {
          scheduled: theme.palette.info.main,
          published: theme.palette.success.main,
          failed: theme.palette.error.main,
        }[post.status],
        extendedProps: { ...post },
      })) || [],
    [posts, theme]
  );

  const handleDateClick = (arg) =>
    setModalState({ open: true, event: null, date: arg.dateStr });
  const handleEventClick = (arg) => {
    const fullPost = posts.find((p) => p.id.toString() === arg.event.id);
    setModalState({ open: true, event: fullPost, date: null });
  };
  const handleCloseModal = () =>
    setModalState({ open: false, event: null, date: null });

  const handleEventDrop = (info) => {
    const { event } = info;
    const postData = {
      post_text: event.title,
      publish_at: event.start.toISOString(),
      attachments: event.extendedProps.attachments,
    };
    updateMutation.mutate({ postId: event.id, data: postData });
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" component="h1" sx={{ fontWeight: 600, mb: 3 }}>
        Планировщик постов
      </Typography>
      <Paper sx={{ p: { xs: 1, sm: 2, md: 3 } }}>
        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <StyledCalendarWrapper>
            <FullCalendar
              plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
              initialView="dayGridMonth"
              headerToolbar={{
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay',
              }}
              events={events}
              editable={true}
              selectable={true}
              selectMirror={true}
              dayMaxEvents={true}
              dateClick={handleDateClick}
              eventClick={handleEventClick}
              eventDrop={handleEventDrop}
              locale="ru"
              buttonText={{
                today: 'Сегодня',
                month: 'Месяц',
                week: 'Неделя',
                day: 'День',
              }}
              height="auto"
            />
          </StyledCalendarWrapper>
        )}
      </Paper>
      <PostEditorModal
        open={modalState.open}
        onClose={handleCloseModal}
        post={modalState.event}
        selectedDate={modalState.date}
      />
    </Box>
  );
};

export default PostsPage;
