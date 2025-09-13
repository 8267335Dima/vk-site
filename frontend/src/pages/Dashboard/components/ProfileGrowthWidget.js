// --- frontend/src/pages/Dashboard/components/ProfileGrowthWidget.js ---
import React, { useState, useMemo } from 'react';
import { Paper, Typography, Box, useTheme, Skeleton, Button, ButtonGroup, Chip, Stack } from '@mui/material';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { useQuery } from '@tanstack/react-query';
// ИСПРАВЛЕНО
import { fetchProfileGrowth } from '../../../api';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { motion } from 'framer-motion';

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <Paper sx={{ p: 2, background: 'rgba(30, 31, 37, 0.9)', backdropFilter: 'blur(5px)', borderRadius: 2 }}>
                <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>{format(new Date(label), 'd MMMM yyyy', { locale: ru })}</Typography>
                {payload.map(p => (
                    <Typography key={p.name} variant="body2" sx={{ color: p.color }}>
                        {`${p.name}: ${p.value.toLocaleString('ru-RU')}`}
                    </Typography>
                ))}
            </Paper>
        );
    }
    return null;
};

export default function ProfileGrowthWidget() {
    const [dataType, setDataType] = useState('likes');
    const theme = useTheme();
    const { data, isLoading } = useQuery({
        queryKey: ['profileGrowth'],
        queryFn: () => fetchProfileGrowth(30),
        staleTime: 1000 * 60 * 60,
    });

    const { chartData, dailyDelta } = useMemo(() => {
        if (!data?.data) return { chartData: [], dailyDelta: null };
        const chartData = data.data.map(item => ({
            date: new Date(item.date).getTime(),
            value: dataType === 'likes' ? item.total_likes_on_content : item.friends_count,
        }));
        
        let dailyDelta = null;
        if (chartData.length >= 2) {
            const last = chartData[chartData.length - 1].value;
            const prev = chartData[chartData.length - 2].value;
            dailyDelta = last - prev;
        }

        return { chartData, dailyDelta };
    }, [data, dataType]);
    
    const metricName = dataType === 'likes' ? 'Сумма лайков' : 'Количество друзей';
    const deltaColor = dailyDelta > 0 ? 'success' : dailyDelta < 0 ? 'error' : 'default';

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }} component={motion.div} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>Динамика роста профиля</Typography>
                <ButtonGroup size="small">
                    <Button variant={dataType === 'likes' ? 'contained' : 'outlined'} onClick={() => setDataType('likes')}>Лайки</Button>
                    <Button variant={dataType === 'friends' ? 'contained' : 'outlined'} onClick={() => setDataType('friends')}>Друзья</Button>
                </ButtonGroup>
            </Stack>
            <Box sx={{ mb: 2, height: 24 }}>
                {dailyDelta !== null && !isLoading && (
                    <Chip
                        icon={dailyDelta > 0 ? <ArrowUpwardIcon /> : <ArrowDownwardIcon />}
                        label={` ${dailyDelta > 0 ? '+' : ''}${dailyDelta.toLocaleString('ru-RU')} за сутки`}
                        color={deltaColor}
                        size="small"
                        variant="outlined"
                    />
                )}
            </Box>
            {isLoading ? (
                <Skeleton variant="rounded" height={250} />
            ) : (
                <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                        <XAxis 
                            dataKey="date" 
                            stroke={theme.palette.text.secondary} 
                            tickFormatter={(timeStr) => format(new Date(timeStr), 'd MMM', { locale: ru })}
                            fontSize="0.8rem"
                        />
                        <YAxis stroke={theme.palette.text.secondary} fontSize="0.8rem" domain={['dataMin - 10', 'dataMax + 10']} allowDataOverflow />
                        <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                        <Tooltip content={<CustomTooltip />} />
                        <Line type="monotone" dataKey="value" name={metricName} stroke={theme.palette.secondary.main} strokeWidth={3} dot={false} activeDot={{ r: 8 }} />
                    </LineChart>
                </ResponsiveContainer>
            )}
        </Paper>
    );
}