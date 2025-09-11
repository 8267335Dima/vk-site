// frontend/src/pages/Scenarios/ScenarioEditorModal.js
import React, { useState, useEffect, useRef } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Stack, CircularProgress } from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createScenario, updateScenario } from 'api';
import { toast } from 'react-hot-toast';
import AddIcon from '@mui/icons-material/Add';
import { CronBuilder } from './components/CronBuilder';
import { ScenarioStepList } from './components/ScenarioStepList';

const ScenarioEditorModal = ({ open, onClose, scenario }) => {
    const queryClient = useQueryClient();
    const [name, setName] = useState('');
    const [schedule, setSchedule] = useState('0 9 * * 1,2,3,4,5');
    const [steps, setSteps] = useState([]);
    const localIdCounter = useRef(0);

    useEffect(() => {
        if (open) {
            localIdCounter.current = 0; 
            if (scenario) {
                setName(scenario.name);
                setSchedule(scenario.schedule);
                setSteps(scenario.steps.map(s => ({ ...s, localId: localIdCounter.current++ })));
            } else {
                setName('');
                setSchedule('0 9 * * 1,2,3,4,5');
                setSteps([{ localId: localIdCounter.current++, action_type: 'like_feed', settings: { count: 50, filters: {} } }]);
            }
        }
    }, [scenario, open]);

    const mutation = useMutation({
        mutationFn: scenario ? updateScenario : createScenario,
        onSuccess: () => {
            toast.success(`Сценарий успешно ${scenario ? 'обновлен' : 'создан'}!`);
            queryClient.invalidateQueries({ queryKey: ['scenarios'] });
            onClose();
        },
        onError: (err) => toast.error(err.response?.data?.detail || 'Ошибка сохранения'),
    });
    
    const handleAddStep = () => setSteps([...steps, { localId: localIdCounter.current++, action_type: 'like_feed', settings: { count: 50, filters: {} } }]);
    const handleRemoveStep = (localId) => setSteps(steps.filter(s => s.localId !== localId));
    const handleStepChange = (localId, field, value) => setSteps(steps.map(s => s.localId === localId ? { ...s, [field]: value } : s));
    
    const handleSave = () => {
        if (!name.trim()) {
            toast.error("Название сценария не может быть пустым.");
            return;
        }
         if (steps.length === 0) {
            toast.error("Добавьте хотя бы один шаг в сценарий.");
            return;
        }
        const payload = {
            name, schedule,
            is_active: scenario?.is_active ?? false,
            steps: steps.map((step, index) => ({
                step_order: index + 1, action_type: step.action_type, settings: step.settings,
            })),
        };
        if (scenario) payload.id = scenario.id;
        mutation.mutate(payload);
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle sx={{ fontWeight: 600 }}>{scenario ? 'Редактировать сценарий' : 'Новый сценарий'}</DialogTitle>
            <DialogContent dividers>
                <Stack spacing={3} py={2}>
                    <TextField label="Название сценария" value={name} onChange={(e) => setName(e.target.value)} />
                    <CronBuilder schedule={schedule} setSchedule={setSchedule} />
                    <ScenarioStepList 
                        steps={steps}
                        setSteps={setSteps}
                        onStepChange={handleStepChange}
                        onStepRemove={handleRemoveStep}
                    />
                    <Button startIcon={<AddIcon />} onClick={handleAddStep} sx={{ alignSelf: 'flex-start' }}>Добавить шаг</Button>
                </Stack>
            </DialogContent>
            <DialogActions sx={{ p: 2 }}>
                <Button onClick={onClose}>Отмена</Button>
                <Button onClick={handleSave} variant="contained" disabled={mutation.isLoading}>
                    {mutation.isLoading ? <CircularProgress size={24} /> : 'Сохранить'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default ScenarioEditorModal;