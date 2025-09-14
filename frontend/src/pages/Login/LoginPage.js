import React, { useState } from 'react';
import {
  Paper,
  Typography,
  TextField,
  Button,
  CircularProgress,
  Alert,
  Box,
  Tooltip,
  Container,
} from '@mui/material';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { motion } from 'framer-motion';

import { loginWithVkToken } from '@/shared/api';
import { useStoreActions } from '@/app/store';
import { content } from '@/shared/config/content';

const getErrorMessage = (error) => {
  if (typeof error?.response?.data?.detail === 'string') {
    return error.response.data.detail;
  }
  return content.loginPage.errors.default;
};

export default function LoginPage() {
  const { login } = useStoreActions();
  const [vkTokenInput, setVkTokenInput] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const handleTokenLogin = async () => {
    if (!vkTokenInput.trim()) {
      setMessage(content.loginPage.errors.emptyToken);
      return;
    }

    let tokenToUse = vkTokenInput.trim();
    if (tokenToUse.includes('access_token=')) {
      try {
        const params = new URLSearchParams(tokenToUse.split('#')[1]);
        tokenToUse = params.get('access_token');
        if (!tokenToUse) throw new Error();
      } catch {
        setMessage(content.loginPage.errors.invalidUrl);
        return;
      }
    }

    setLoading(true);
    setMessage('');
    try {
      const response = await loginWithVkToken(tokenToUse);
      login(response.data);
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      setMessage(errorMessage);
    }
    setLoading(false);
  };

  return (
    <Container
      maxWidth="sm"
      sx={{ display: 'flex', alignItems: 'center', py: { xs: 4, md: 12 } }}
    >
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{ width: '100%' }}
      >
        <Paper sx={{ p: { xs: 3, md: 5 }, textAlign: 'center' }}>
          <Typography
            component="h1"
            variant="h4"
            gutterBottom
            sx={{ fontWeight: 700 }}
          >
            {content.loginPage.title}
          </Typography>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 1,
              mb: 4,
            }}
          >
            <Typography variant="body1" color="text.secondary">
              {content.loginPage.subtitle}
            </Typography>
            <Tooltip
              title={
                <Box sx={{ textAlign: 'left', p: 1 }}>
                  <Typography
                    variant="body2"
                    display="block"
                    sx={{ mb: 1.5 }}
                    dangerouslySetInnerHTML={{
                      __html: content.loginPage.tooltip.step1,
                    }}
                  />
                  <Typography variant="body2" display="block" sx={{ mb: 1.5 }}>
                    {content.loginPage.tooltip.step2}
                  </Typography>
                  <Typography variant="body2" display="block">
                    {content.loginPage.tooltip.step3}
                  </Typography>
                </Box>
              }
              placement="top"
              arrow
            >
              <HelpOutlineIcon
                fontSize="small"
                color="secondary"
                sx={{ cursor: 'help' }}
              />
            </Tooltip>
          </Box>
          <TextField
            fullWidth
            label={content.loginPage.textFieldLabel}
            variant="outlined"
            value={vkTokenInput}
            onChange={(e) => setVkTokenInput(e.target.value)}
            onKeyPress={(e) =>
              e.key === 'Enter' && !loading && handleTokenLogin()
            }
            sx={{ mb: 2 }}
          />
          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={handleTokenLogin}
            disabled={loading}
            sx={{ py: 1.5, fontSize: '1.1rem' }}
          >
            {loading ? (
              <CircularProgress size={26} color="inherit" />
            ) : (
              content.loginPage.buttonText
            )}
          </Button>
          {message && (
            <Alert
              severity={'error'}
              sx={{ mt: 3, textAlign: 'left', borderRadius: 2 }}
            >
              {message}
            </Alert>
          )}
        </Paper>
      </motion.div>
    </Container>
  );
}
