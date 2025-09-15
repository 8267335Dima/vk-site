import React, { useMemo, useState } from 'react';
import {
  Paper,
  Typography,
  useTheme,
  Grid,
  Skeleton,
  Tooltip,
  IconButton,
  Stack,
  alpha,
  Box,
} from '@mui/material';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  PieChart,
  Pie,
  Cell,
  Sector,
} from 'recharts';
import { useQuery } from '@tanstack/react-query';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { motion } from 'framer-motion';

import { fetchAudienceAnalytics } from '@/shared/api';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <Paper
        sx={{
          p: 2,
          background: 'rgba(30, 31, 37, 0.9)',
          backdropFilter: 'blur(5px)',
          borderRadius: 2,
        }}
      >
        <Typography variant="body2">{`${label}: ${payload[0].value.toLocaleString(
          'ru-RU'
        )}`}</Typography>
      </Paper>
    );
  }
  return null;
};

const renderActiveShape = (props) => {
  const {
    cx,
    cy,
    innerRadius,
    outerRadius,
    startAngle,
    endAngle,
    fill,
    payload,
    percent,
  } = props;

  return (
    <g>
      <text
        x={cx}
        y={cy}
        dy={-10}
        textAnchor="middle"
        fill={fill}
        fontSize="1.2rem"
        fontWeight={700}
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
      <text
        x={cx}
        y={cy}
        dy={12}
        textAnchor="middle"
        fill={fill}
        fontSize="0.9rem"
      >
        {payload.name}
      </text>
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius}
        outerRadius={outerRadius}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
      />
      <Sector
        cx={cx}
        cy={cy}
        startAngle={startAngle}
        endAngle={endAngle}
        innerRadius={outerRadius + 6}
        outerRadius={outerRadius + 10}
        fill={fill}
      />
    </g>
  );
};

export default function AudienceAnalyticsWidget() {
  const theme = useTheme();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['audienceAnalytics'],
    queryFn: fetchAudienceAnalytics,
    staleTime: 1000 * 60 * 60,
  });
  const [activeIndex, setActiveIndex] = useState(0);

  const onPieEnter = (_, index) => setActiveIndex(index);

  const chartData = useMemo(() => {
    return {
      city: data?.city_distribution || [],
      age: data?.age_distribution || [],
      sex: data?.sex_distribution || [],
    };
  }, [data]);

  const COLORS = [
    theme.palette.primary.main,
    theme.palette.secondary.main,
    theme.palette.warning.main,
    theme.palette.success.main,
    theme.palette.info.main,
  ];

  const renderContent = () => {
    if (isLoading) return <Skeleton variant="rounded" height={250} />;
    if (isError)
      return (
        <Typography color="error.main">Ошибка загрузки аналитики.</Typography>
      );
    if (!data || !data.sex_distribution || data.sex_distribution.length === 0)
      return (
        <Box
          sx={{
            display: 'flex',
            height: 250,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography color="text.secondary">
            Нет данных для анализа.
          </Typography>
        </Box>
      );

    return (
      <Grid container spacing={3} alignItems="center">
        <Grid item xs={12} md={5}>
          <Typography
            variant="subtitle1"
            sx={{ fontWeight: 600, textAlign: 'center', mb: 1 }}
          >
            Пол
          </Typography>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={chartData.sex}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                activeIndex={activeIndex}
                activeShape={renderActiveShape}
                onMouseEnter={onPieEnter}
              >
                {chartData.sex.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </Grid>
        <Grid item xs={12} md={7}>
          <Typography
            variant="subtitle1"
            sx={{ fontWeight: 600, textAlign: 'center', mb: 1 }}
          >
            Топ городов
          </Typography>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={chartData.city}
              layout="vertical"
              margin={{ top: 5, right: 20, left: 80, bottom: 5 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={80}
                tick={{
                  fill: theme.palette.text.secondary,
                  fontSize: '0.8rem',
                }}
                tickLine={false}
                axisLine={false}
                interval={0}
              />
              <RechartsTooltip
                content={<CustomTooltip />}
                cursor={{ fill: alpha(theme.palette.primary.main, 0.1) }}
              />
              <Bar dataKey="value" barSize={20} radius={[0, 8, 8, 0]}>
                {chartData.city.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Grid>
      </Grid>
    );
  };

  return (
    <Paper
      sx={{ p: 3, height: '100%' }}
      component={motion.div}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2 }}
      >
        <Typography variant="h6" sx={{ fontWeight: 600, m: 0 }}>
          Анализ аудитории
        </Typography>
        <Tooltip
          title="Анализ на основе ваших друзей. Данные периодически обновляются для поддержания актуальности."
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
}
