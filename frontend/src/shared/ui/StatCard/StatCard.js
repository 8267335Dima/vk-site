import React from 'react';
import { Paper, Typography, Box, Skeleton, alpha } from '@mui/material';
import { motion } from 'framer-motion';

// УЛУЧШЕНИЕ: Оборачиваем в React.memo, так как это чисто презентационный
// компонент, который зависит только от своих пропсов.
const StatCard = React.memo(
  ({ title, value, icon, isLoading, color = 'primary' }) => {
    return (
      <motion.div
        whileHover={{ y: -5 }}
        transition={{ type: 'spring', stiffness: 300 }}
      >
        <Paper
          sx={{
            p: 2.5,
            display: 'flex',
            alignItems: 'center',
            gap: 3,
            height: '100%',
            position: 'relative',
            overflow: 'hidden',
            background: (theme) =>
              `linear-gradient(135deg, ${alpha(
                theme.palette[color].dark,
                0.15
              )} 0%, ${alpha(theme.palette.background.paper, 0.15)} 100%)`,
            borderColor: (theme) => alpha(theme.palette[color].main, 0.3),
          }}
        >
          <Box
            sx={{
              position: 'absolute',
              right: -20,
              bottom: -20,
              color: `${color}.main`,
              fontSize: '120px',
              opacity: 0.05,
              transform: 'rotate(-20deg)',
              pointerEvents: 'none',
            }}
          >
            {icon}
          </Box>

          <Box>
            <Typography
              variant="body1"
              color="text.secondary"
              sx={{ fontWeight: 500 }}
            >
              {title}
            </Typography>
            {isLoading ? (
              <Skeleton variant="text" width={80} height={40} />
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                key={value}
              >
                <Typography variant="h4" sx={{ fontWeight: 700, mt: 0.5 }}>
                  {value?.toLocaleString('ru-RU') || 0}
                </Typography>
              </motion.div>
            )}
          </Box>
        </Paper>
      </motion.div>
    );
  }
);

StatCard.displayName = 'StatCard';

export default StatCard;
