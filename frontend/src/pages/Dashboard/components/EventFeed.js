// frontend/src/pages/Dashboard/components/EventFeed.js
import React, { useRef, useEffect } from 'react';
import { Box, Typography, Link, Paper } from '@mui/material';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { useWebSocketContext } from 'contexts/WebSocketProvider';
import { dashboardContent } from 'content/dashboardContent';
import { motion, AnimatePresence } from 'framer-motion';

const statusStyles = {
  success: { color: 'success.main', symbol: '✓' },
  info: { color: 'text.secondary', symbol: 'i' },
  warning: { color: 'warning.main', symbol: '!' },
  error: { color: 'error.main', symbol: '✗' },
  debug: { color: 'grey.600', symbol: '•' },
};

export default function EventFeed() {
  const wsContext = useWebSocketContext();
  // --- ИСПРАВЛЕНИЕ: Получаем logs напрямую. Если их нет, будет undefined. ---
  const logs = wsContext?.logs; 
  const scrollRef = useRef(null);
  const { title, waiting, link } = dashboardContent.eventFeed;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]); // Теперь зависимость стабильна

  return (
    <Paper sx={{ p: 3, display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Typography variant="h5" gutterBottom sx={{ fontWeight: 600 }}>{title}</Typography>
      <Box
        ref={scrollRef}
        sx={{
          flexGrow: 1, p: 2, overflowY: 'auto',
          fontFamily: '"Fira Code", "Roboto Mono", monospace',
          fontSize: '0.85rem', backgroundColor: 'rgba(0,0,0,0.2)',
          borderRadius: 3, minHeight: '400px',
        }}
      >
        {/* --- ИСПРАВЛЕНИЕ: Проверяем logs?.length --- */}
        {!logs?.length ? (
          <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary" sx={{ fontFamily: 'inherit' }}>{waiting}</Typography>
          </Box>
        ) : (
          <AnimatePresence>
            {logs.map((log, index) => {
              const style = statusStyles[log.status] || statusStyles.info;
              return (
                <motion.div
                  key={log.timestamp + index}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <Box sx={{ display: 'flex', gap: 1.5, mb: 1, alignItems: 'flex-start' }}>
                    <Typography component="span" color="text.secondary" sx={{ flexShrink: 0 }}>
                      [{format(new Date(log.timestamp), 'HH:mm:ss', { locale: ru })}]
                    </Typography>
                    <Typography component="span" sx={{ color: style.color, wordBreak: 'break-word', flexGrow: 1 }}>
                      <Typography component="span" sx={{ mr: 1, fontWeight: 'bold' }}>{style.symbol}</Typography>
                      {log.message}
                      {log.url && <Link href={log.url} target="_blank" rel="noopener noreferrer" sx={{ ml: 1, fontWeight: 'bold' }}>{link}</Link>}
                    </Typography>
                  </Box>
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </Box>
    </Paper>
  );
}