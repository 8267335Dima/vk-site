// frontend/src/pages/Dashboard/components/FriendsDynamicWidget.js
import React from 'react';
import { Paper, Typography, Box, useTheme, Skeleton, Stack, Tooltip, IconButton } from '@mui/material';
import Chart from 'react-apexcharts';
import { useQuery } from '@tanstack/react-query';
import { fetchFriendsDynamic } from 'api';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

export default function FriendsDynamicWidget() {
    const theme = useTheme();

    const { data: dynamicData, isLoading, isError } = useQuery({
        queryKey: ['friendsDynamic'],
        queryFn: () => fetchFriendsDynamic(30),
        staleTime: 1000 * 60 * 60 * 4,
        refetchOnWindowFocus: false,
    });

    const series = [{
        name: "Всего друзей",
        data: dynamicData?.data.map(item => [new Date(item.date).getTime(), item.total_friends]) || []
    }];

    const options = {
        chart: { type: 'area', height: 200, toolbar: { show: false }, zoom: { enabled: false } },
        dataLabels: { enabled: false },
        stroke: { curve: 'smooth', width: 3 },
        xaxis: {
            // <<-- И УКАЗЫВАЕМ ПРАВИЛЬНЫЙ ТИП ОСИ
            type: 'datetime',
            labels: { format: 'dd MMM', style: { colors: theme.palette.text.secondary } },
            tooltip: { enabled: false },
        },
        yaxis: { labels: { style: { colors: theme.palette.text.secondary } } },
        tooltip: {
            theme: theme.palette.mode,
            x: { format: 'dd MMMM yyyy, dddd' },
        },
        fill: { type: 'gradient', gradient: { shade: 'dark', type: 'vertical', shadeIntensity: 0.5, opacityFrom: 0.7, opacityTo: 0.1, stops: [0, 100] } },
        colors: [theme.palette.primary.main],
        grid: { borderColor: theme.palette.divider, strokeDashArray: 4 }
    };
    
    const renderContent = () => {
        if (isLoading) {
            return <Skeleton variant="rectangular" height={200} sx={{ borderRadius: 2 }} />;
        }
        if (isError) {
            return <Typography color="error.main" sx={{ p: 2 }}>Ошибка загрузки данных.</Typography>;
        }
        // Отличная проверка на случай, если данных еще мало
        if (!dynamicData?.data || dynamicData.data.length < 2) {
            return <Typography color="text.secondary" sx={{ p: 2 }}>Сбор данных... График появится в течение 24 часов.</Typography>;
        }
        return <Chart options={options} series={series} type="area" height={200} width="100%" />;
    };

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, m: 0 }}>
                    Динамика друзей
                </Typography>
                <Tooltip title="График показывает общее количество друзей за последние 30 дней. Данные обновляются раз в сутки." arrow>
                    <IconButton size="small"><InfoOutlinedIcon fontSize='small' /></IconButton>
                </Tooltip>
             </Stack>
            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {renderContent()}
            </Box>
        </Paper>
    );
}