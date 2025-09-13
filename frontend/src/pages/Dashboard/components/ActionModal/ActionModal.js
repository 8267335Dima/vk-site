// frontend/src/pages/Dashboard/components/ActionModal/ActionModal.js
import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, CircularProgress } from '@mui/material';
import { useForm, FormProvider } from 'react-hook-form';
import { ActionModalContent } from './ActionModalContent';
// ИСПРАВЛЕНО
import { useActionTask } from '../../../../hooks/useActionTask';

const ActionModal = ({ open, onClose, actionKey, title }) => {
    const methods = useForm();
    const { mutate: runAction, isLoading } = useActionTask(actionKey, title, onClose);

    const onSubmit = (data) => {
        // RHF уже предоставляет данные в нужном формате.
        // Дополнительная очистка не требуется.
        runAction(data);
    };

    if (!open) return null;

    return (
        <FormProvider {...methods}>
            <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm" PaperProps={{ sx: { borderRadius: 4 } }}>
                <form onSubmit={methods.handleSubmit(onSubmit)}>
                    <DialogTitle sx={{ fontWeight: 600, pb: 1 }}>{title}</DialogTitle>
                    <DialogContent dividers>
                        <ActionModalContent actionKey={actionKey} />
                    </DialogContent>
                    <DialogActions sx={{ p: 2 }}>
                        <Button onClick={onClose} disabled={isLoading}>Отмена</Button>
                        <Button type="submit" variant="contained" disabled={isLoading}>
                            {isLoading ? <CircularProgress size={24} /> : 'Запустить'}
                        </Button>
                    </DialogActions>
                </form>
            </Dialog>
        </FormProvider>
    );
};

export default ActionModal;