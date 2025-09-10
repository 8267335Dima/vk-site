// frontend/src/pages/Dashboard/components/FriendsAnalyticsWidget.js
import React from 'react';
import { Paper, Typography, Box, useTheme, Skeleton } from '@mui/material';
import Chart from 'react-apexcharts';
import { useQuery } from '@tanstack/react-query';
import { fetchFriendsAnalytics } from 'api';
import { dashboardContent } from 'content/dashboardContent';

export default function FriendsAnalyticsWidget() {
    const theme = useTheme();
    const { friendsAnalytics: content } = dashboardContent;

    const { data, isLoading, isError } = useQuery({
        queryKey: ['friendsAnalytics'],
        queryFn: fetchFriendsAnalytics,
        staleTime: 1000 * 60 * 15,
        refetchOnWindowFocus: false,
    });

    const series = React.useMemo(() => {
        // --- ИСПРАВЛЕНИЕ: Проверяем, что data существует и имеет нужные поля ---
        if (data && typeof data.female_count !== 'undefined') {
            return [data.female_count, data.male_count, data.other_count];
        }
        return [];
    }, [data]);

    const totalFriends = series.reduce((a, b) => a + b, 0);

    const options = {
        chart: { type: 'donut', animations: { enabled: true, speed: 800 } },
        labels: content.labels,
        colors: [theme.palette.primary.light, theme.palette.info.light, theme.palette.grey[400]],
        plotOptions: {
            pie: {
                donut: {
                    size: '70%',
                    labels: {
                        show: true,
                        name: { show: false },
                        value: {
                            show: true,
                            fontSize: '24px',
                            fontWeight: 700,
                            color: theme.palette.text.primary,
                            formatter: (val) => val,
                        },
                        total: {
                            show: true,
                            showAlways: true,
                            label: content.total,
                            fontSize: '14px',
                            color: theme.palette.text.secondary,
                            formatter: () => totalFriends,
                        }
                    }
                }
            }
        },
        dataLabels: { enabled: false },
        legend: { show: true, position: 'bottom', horizontalAlign: 'center', fontSize: '14px', fontWeight: 500, markers: { width: 12, height: 12, radius: 6 }, itemMargin: { horizontal: 10, vertical: 5 } },
        tooltip: { y: { formatter: (val) => `${val} ${content.tooltipSuffix}` } },
        stroke: { width: 0 }
    };

    const renderContent = () => {
        if (isLoading) {
            return <Skeleton variant="circular" width={200} height={200} />;
        }
        if (isError) {
            return <Typography color="error.main" variant="body2">{content.error}</Typography>;
        }
        if (totalFriends > 0) {
            return <Chart options={options} series={series} type="donut" width="100%" height={280} />;
        }
        return <Typography color="text.secondary">{content.noData}</Typography>;
    };

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>{content.title}</Typography>
            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 280 }}>
                {renderContent()}
            </Box>
        </Paper>
    );
}