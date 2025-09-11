// frontend/src/pages/Home/components/FeatureHighlightCard.js
import React from 'react';
import { Stack, Box, Typography } from '@mui/material';
import { motion } from 'framer-motion';

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};

const FeatureHighlightCard = ({ icon, title, description }) => {
    return (
        <motion.div variants={fadeInUp} style={{ height: '100%' }}>
            <Stack spacing={2} direction="row" sx={{ p: 2 }}>
                <Box sx={{ fontSize: '2.5rem', color: 'secondary.main', mt: 0.5 }}>
                    {icon}
                </Box>
                <Box>
                    <Typography variant="h6" sx={{fontWeight: 600}}>{title}</Typography>
                    <Typography color="text.secondary">{description}</Typography>
                </Box>
            </Stack>
        </motion.div>
    );
};

export default FeatureHighlightCard;