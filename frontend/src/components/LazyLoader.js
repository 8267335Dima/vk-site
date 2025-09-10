// frontend/src/components/LazyLoader.js
import React from 'react';
import { Box, CircularProgress, Skeleton } from '@mui/material';

// Можно выбрать один из вариантов или комбинировать
const LazyLoader = ({ variant = 'circular' }) => {
    if (variant === 'skeleton') {
        return <Skeleton variant="rectangular" width="100%" height="100%" sx={{ borderRadius: 4 }} />;
    }

    return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', height: '100%' }}>
            <CircularProgress />
        </Box>
    );
};

export default LazyLoader;