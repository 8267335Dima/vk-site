import React from 'react';
import { Grid } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import GroupIcon from '@mui/icons-material/Group';
import RssFeedIcon from '@mui/icons-material/RssFeed';
import PhotoLibraryIcon from '@mui/icons-material/PhotoLibrary';
import ArticleIcon from '@mui/icons-material/Article';

import { fetchProfileSummary } from '@/shared/api';
import StatCard from '@/shared/ui/StatCard/StatCard';

const ProfileSummaryWidget = () => {
  const { data, isLoading } = useQuery({
    queryKey: ['profileSummary'],
    queryFn: fetchProfileSummary,
    staleTime: 1000 * 60 * 60,
  });

  const stats = [
    {
      title: 'Друзья',
      value: data?.friends,
      icon: <GroupIcon />,
      color: 'primary',
    },
    {
      title: 'Подписчики',
      value: data?.followers,
      icon: <RssFeedIcon />,
      color: 'secondary',
    },
    {
      title: 'Фотографии',
      value: data?.photos,
      icon: <PhotoLibraryIcon />,
      color: 'success',
    },
    {
      title: 'Записи на стене',
      value: data?.wall_posts,
      icon: <ArticleIcon />,
      color: 'warning',
    },
  ];

  return (
    <Grid container spacing={2} sx={{ height: '100%' }}>
      {stats.map((stat, index) => (
        <Grid
          item
          xs={12}
          sm={6}
          key={index}
          component={motion.div}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.1 }}
        >
          <StatCard
            title={stat.title}
            value={isLoading ? 0 : stat.value}
            icon={stat.icon}
            color={stat.color}
            isLoading={isLoading}
          />
        </Grid>
      ))}
    </Grid>
  );
};

export default ProfileSummaryWidget;
