// frontend/src/pages/Dashboard/components/AudienceAnalyticsWidget.js
import React, { useMemo } from 'react';
import { Paper, Typography, Box, useTheme, Grid, Skeleton, Tooltip, IconButton, Stack } from '@mui/material';
import Chart from 'react-apexcharts';
import { useQuery } from '@tanstack/react-query';
import { fetchAudienceAnalytics } from 'api';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

const ChartWrapper = ({ title, options, series, type, isLoading }) => (
    <Box>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, textAlign: 'center', mb: 1 }}>
            {title}
        </Typography>
        {isLoading ? (
            <Skeleton variant="rectangular" height={220} sx={{ borderRadius: 2 }}/>
        ) : (
            <Chart options={options} series={series} type={type} height={220} />
        )}
    </Box>
);

export default function AudienceAnalyticsWidget() {
    const theme = useTheme();

    const { data, isLoading, isError } = useQuery({
        queryKey: ['audienceAnalytics'],
        queryFn: fetchAudienceAnalytics,
        staleTime: 1000 * 60 * 60,
    });

    // --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Безопасно обрабатываем данные с помощью useMemo ---
    const chartData = useMemo(() => {
        const cityDistribution = Array.isArray(data?.city_distribution) ? data.city_distribution : [];
        const ageDistribution = Array.isArray(data?.age_distribution) ? data.age_distribution : [];

        return {
            city: {
                series: [{ name: 'Друзей', data: cityDistribution.map(c => c.value) }],
                categories: cityDistribution.map(c => c.name),
            },
            age: {
                series: ageDistribution.map(a => a.value),
                labels: ageDistribution.map(a => a.name),
            }
        };
    }, [data]);

    const commonOptions = {
        chart: { animations: { enabled: true }, toolbar: { show: false } },
        dataLabels: { enabled: false },
        tooltip: { theme: theme.palette.mode },
        legend: { show: false },
    };

    const cityChartOptions = {
        ...commonOptions,
        plotOptions: { bar: { borderRadius: 4, horizontal: true, barHeight: '70%' } },
        xaxis: {
            categories: chartData.city.categories, // <--- Используем безопасные данные
            labels: { style: { colors: theme.palette.text.secondary } }
        },
        yaxis: { labels: { style: { colors: theme.palette.text.secondary } } },
        colors: [theme.palette.secondary.main]
    };

    const ageChartOptions = {
        ...commonOptions,
        labels: chartData.age.labels, // <--- Используем безопасные данные
        plotOptions: { pie: { donut: { size: '65%' } } },
        colors: ['#7E57C2', '#5C6BC0', '#42A5F5', '#29B6F6', '#26A69A', '#66BB6A']
    };

    const renderContent = () => {
        if (isError) return <Typography color="error.main" sx={{p: 2}}>Ошибка загрузки аналитики.</Typography>;
        if (!isLoading && !chartData.city.categories.length && !chartData.age.labels.length) {
            return <Typography color="text.secondary" sx={{p: 2}}>Недостаточно данных для анализа.</Typography>;
        }

        return (
            <Grid container spacing={1} alignItems="center">
                <Grid item xs={12} sm={6}>
                    <ChartWrapper title="Топ городов" options={cityChartOptions} series={chartData.city.series} type="bar" isLoading={isLoading} />
                </Grid>
                <Grid item xs={12} sm={6}>
                    <ChartWrapper title="Возраст" options={ageChartOptions} series={chartData.age.series} type="donut" isLoading={isLoading} />
                </Grid>
            </Grid>
        );
    };

    return (
        <Paper sx={{ p: 3, height: '100%' }}>
             <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, m: 0 }}>
                    Анализ аудитории
                </Typography>
                <Tooltip title="Анализ проводится по топ-1000 друзей с открытыми профилями. Данные кешируются на 6 часов." arrow>
                    <IconButton size="small"><InfoOutlinedIcon fontSize='small' /></IconButton>
                </Tooltip>
             </Stack>
            {renderContent()}
        </Paper>
    );
}