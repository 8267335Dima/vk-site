// frontend/src/pages/Dashboard/components/ProfileGrowthWidget.js
import React, { useState, useMemo } from 'react';
import { Paper, Typography, Box, useTheme, Skeleton, Button, ButtonGroup } from '@mui/material';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { fetchProfileGrowth } from 'api.js';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <Paper sx={{ p: 2, background: 'rgba(30, 31, 37, 0.9)', backdropFilter: 'blur(5px)', borderRadius: 2 }}>
                <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>{format(new Date(label), 'd MMMM yyyy', { locale: ru })}</Typography>
                {payload.map(p => (
                    <Typography key={p.name} variant="body2" sx={{ color: p.color }}>
                        {`${p.name}: ${p.value}`}
                    </Typography>
                ))}
            </Paper>
        );
    }
    return null;
};

export default function ProfileGrowthWidget() {
    const [dataType, setDataType] = useState('likes'); // 'likes' or 'friends'
    const theme = useTheme();
    const { data, isLoading } = useQuery({
        queryKey: ['profileGrowth'],
        queryFn: () => fetchProfileGrowth(30),
        staleTime: 1000 * 60 * 60, // 1 hour
    });

    const chartData = useMemo(() => {
        if (!data?.data) return [];
        return data.data.map(item => ({
            date: new Date(item.date).getTime(),
            value: dataType === 'likes' ? item.total_likes_on_content : item.friends_count,
        }));
    }, [data, dataType]);
    
    const metricName = dataType === 'likes' ? 'Сумма лайков' : 'Количество друзей';

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>Динамика роста профиля</Typography>
                <ButtonGroup size="small">
                    <Button variant={dataType === 'likes' ? 'contained' : 'outlined'} onClick={() => setDataType('likes')}>Лайки</Button>
                    <Button variant={dataType === 'friends' ? 'contained' : 'outlined'} onClick={() => setDataType('friends')}>Друзья</Button>
                </ButtonGroup>
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
                        <YAxis stroke={theme.palette.text.secondary} fontSize="0.8rem" domain={['dataMin - 10', 'dataMax + 10']} />
                        <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                        <Tooltip content={<CustomTooltip />} />
                        <Line type="monotone" dataKey="value" name={metricName} stroke={theme.palette.secondary.main} strokeWidth={3} dot={false} />
                    </LineChart>
                </ResponsiveContainer>
            )}
        </Paper>
    );
}