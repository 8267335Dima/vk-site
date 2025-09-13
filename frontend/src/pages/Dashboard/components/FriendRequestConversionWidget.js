import React from 'react';
import {
  Paper,
  Typography,
  Box,
  Skeleton,
  Stack,
  Tooltip,
  IconButton,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
} from 'recharts';
import { useTheme } from '@mui/material/styles';
import { motion } from 'framer-motion';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

import { fetchFriendRequestConversion } from '@/shared/api/api';

const FriendRequestConversionWidget = () => {
  const theme = useTheme();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['friendRequestConversion'],
    queryFn: fetchFriendRequestConversion,
    staleTime: 1000 * 60 * 15,
  });

  const conversionRate = data?.conversion_rate || 0;
  const chartData = [{ name: 'conversion', value: conversionRate }];

  const color =
    conversionRate > 75
      ? theme.palette.success.main
      : conversionRate > 40
        ? theme.palette.warning.main
        : theme.palette.error.main;

  const renderContent = () => {
    if (isLoading) {
      return (
        <Skeleton
          variant="circular"
          width={150}
          height={150}
          sx={{ mx: 'auto' }}
        />
      );
    }
    if (isError) {
      return (
        <Typography color="error.main">Ошибка загрузки данных.</Typography>
      );
    }
    if (data?.sent_total === 0) {
      return (
        <Typography color="text.secondary">
          Отправьте заявки в друзья, чтобы увидеть статистику.
        </Typography>
      );
    }

    return (
      <Stack direction="row" alignItems="center" spacing={2}>
        <Box sx={{ width: 150, height: 150, position: 'relative' }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              innerRadius="75%"
              outerRadius="90%"
              data={chartData}
              startAngle={90}
              endAngle={-270}
            >
              <PolarAngleAxis
                type="number"
                domain={[0, 100]}
                angleAxisId={0}
                tick={false}
              />
              <RadialBar
                background
                dataKey="value"
                cornerRadius={10}
                fill={color}
                angleAxisId={0}
              />
            </RadialBarChart>
          </ResponsiveContainer>
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography variant="h4" sx={{ fontWeight: 700, color }}>
              {conversionRate.toFixed(1)}%
            </Typography>
          </Box>
        </Box>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Конверсия заявок
          </Typography>
          <Typography color="text.secondary">
            Принято:{' '}
            <b style={{ color: theme.palette.text.primary }}>
              {data.accepted_total.toLocaleString('ru-RU')}
            </b>
          </Typography>
          <Typography color="text.secondary">
            Отправлено:{' '}
            <b style={{ color: theme.palette.text.primary }}>
              {data.sent_total.toLocaleString('ru-RU')}
            </b>
          </Typography>
        </Box>
      </Stack>
    );
  };

  return (
    <Paper
      sx={{
        p: 3,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        textAlign: 'center',
      }}
      component={motion.div}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <Stack
        direction="row"
        spacing={1}
        sx={{ position: 'absolute', top: 8, right: 8 }}
      >
        <Tooltip
          title="Показывает, какой процент отправленных вами заявок в друзья был принят. Данные обновляются каждые несколько часов."
          arrow
        >
          <IconButton size="small">
            <InfoOutlinedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Stack>
      {renderContent()}
    </Paper>
  );
};

export default FriendRequestConversionWidget;
