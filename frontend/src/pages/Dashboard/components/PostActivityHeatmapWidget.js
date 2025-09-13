// --- frontend/src/pages/Dashboard/components/PostActivityHeatmapWidget.js ---
import React from 'react';
import { Paper, Typography, Box, Skeleton, Tooltip, Stack, alpha } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchPostActivityHeatmap } from 'api';
import { motion } from 'framer-motion';

const daysOfWeek = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const hoursOfDay = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0'));

const HeatmapCell = ({ value }) => {
    const opacity = value / 100;
    return (
        <Tooltip title={`Активность: ${value}%`} placement="top">
            <Box
                sx={{
                    width: '100%',
                    paddingBottom: '100%', // Создает квадрат
                    backgroundColor: theme => alpha(theme.palette.primary.main, opacity),
                    borderRadius: '2px',
                    transition: 'background-color 0.2s ease-in-out',
                    '&:hover': {
                        border: theme => `1px solid ${theme.palette.primary.light}`,
                    }
                }}
            />
        </Tooltip>
    );
};

const PostActivityHeatmapWidget = () => {
    const { data, isLoading } = useQuery({
        queryKey: ['postActivityHeatmap'],
        queryFn: fetchPostActivityHeatmap,
        staleTime: 1000 * 60 * 60, // 1 час
    });

    return (
        <Paper sx={{ p: 3 }} component={motion.div} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                Лучшее время для постинга
            </Typography>
            {isLoading ? (
                <Skeleton variant="rounded" height={200} />
            ) : (
                <Stack spacing={1}>
                    <Box sx={{ display: 'grid', gridTemplateColumns: '30px repeat(24, 1fr)', gap: '4px' }}>
                        <Box />
                        {hoursOfDay.map(hour => (
                            <Typography key={hour} variant="caption" color="text.secondary" textAlign="center">
                                {hour % 2 === 0 ? hour : ''}
                            </Typography>
                        ))}
                    </Box>
                    <Box sx={{ display: 'grid', gridTemplateColumns: '30px repeat(24, 1fr)', gap: '4px' }}>
                        {daysOfWeek.map((day, dayIndex) => (
                            <React.Fragment key={day}>
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center' }}>{day}</Typography>
                                {data?.data[dayIndex].map((value, hourIndex) => (
                                    <HeatmapCell key={`${dayIndex}-${hourIndex}`} value={value} />
                                ))}
                            </React.Fragment>
                        ))}
                    </Box>
                    <Stack direction="row" justifyContent="flex-end" alignItems="center" spacing={1} sx={{ mt: 1 }}>
                        <Typography variant="caption" color="text.secondary">Меньше</Typography>
                        <Box sx={{ width: 15, height: 15, borderRadius: '2px', background: theme => alpha(theme.palette.primary.main, 0.1) }} />
                        <Box sx={{ width: 15, height: 15, borderRadius: '2px', background: theme => alpha(theme.palette.primary.main, 0.4) }} />
                        <Box sx={{ width: 15, height: 15, borderRadius: '2px', background: theme => alpha(theme.palette.primary.main, 0.7) }} />
                        <Box sx={{ width: 15, height: 15, borderRadius: '2px', background: theme => alpha(theme.palette.primary.main, 1.0) }} />
                        <Typography variant="caption" color="text.secondary">Больше</Typography>
                    </Stack>
                </Stack>
            )}
        </Paper>
    );
};

export default PostActivityHeatmapWidget;