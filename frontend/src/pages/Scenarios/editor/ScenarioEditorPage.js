import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Box,
  Paper,
  Button,
  CircularProgress,
  TextField,
  Switch,
  FormControlLabel,
} from '@mui/material';
import ReactFlow, {
  ReactFlowProvider,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  addEdge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';

import {
  fetchScenarioById,
  createScenario,
  updateScenario,
} from '@/shared/api/api';
import { CronBuilder } from '../components/CronBuilder';
import Sidebar from './Sidebar';
import ActionNode from './nodes/ActionNode';
import ConditionNode from './nodes/ConditionNode';
import StartNode from './nodes/StartNode';

const nodeTypes = {
  action: ActionNode,
  condition: ConditionNode,
  start: StartNode,
};

let idCounter = 1;
const getUniqueNodeId = () => `dndnode_${Date.now()}_${idCounter++}`;

const ScenarioEditorPage = () => {
  const { id: scenarioId } = useParams();
  const isNew = scenarioId === 'new';
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const reactFlowWrapper = useRef(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);

  const [name, setName] = useState('');
  const [schedule, setSchedule] = useState('0 9 * * *');
  const [isActive, setIsActive] = useState(false);

  const handleNodeDataChange = useCallback(
    (nodeId, newData) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return { ...node, data: { ...node.data, ...newData } };
          }
          return node;
        })
      );
    },
    [setNodes]
  );

  const { isLoading: isLoadingScenario } = useQuery({
    queryKey: ['scenario', scenarioId],
    queryFn: () => fetchScenarioById(scenarioId),
    enabled: !isNew,
    onSuccess: (data) => {
      if (data) {
        setName(data.name);
        setSchedule(data.schedule);
        setIsActive(data.is_active);
        setNodes(
          data.nodes.map((n) => ({
            ...n,
            data: {
              ...n.data,
              onDataChange: (newData) => handleNodeDataChange(n.id, newData),
            },
          })) || []
        );
        setEdges(data.edges || []);
      }
    },
  });

  useEffect(() => {
    if (isNew) {
      setNodes([
        {
          id: 'start',
          type: 'start',
          position: { x: 250, y: 25 },
          data: { id: 'start', type: 'start', onDataChange: () => {} },
        },
      ]);
      setEdges([]);
    }
  }, [isNew, setNodes, setEdges, handleNodeDataChange]);

  const mutation = useMutation({
    mutationFn: (data) =>
      isNew ? createScenario(data) : updateScenario(scenarioId, data),
    onSuccess: () => {
      toast.success(`Сценарий успешно ${isNew ? 'создан' : 'обновлен'}!`);
      queryClient.invalidateQueries({ queryKey: ['scenarios'] });
      navigate('/scenarios');
    },
    onError: (err) =>
      toast.error(err.response?.data?.detail || 'Ошибка сохранения'),
  });

  const onConnect = useCallback(
    (params) =>
      setEdges((eds) =>
        addEdge({ ...params, type: 'smoothstep', animated: true }, eds)
      ),
    [setEdges]
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const type = event.dataTransfer.getData('application/reactflow');
      if (typeof type === 'undefined' || !type) return;

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      const newNodeId = getUniqueNodeId();
      const newNode = {
        id: newNodeId,
        type,
        position,
        data: {
          id: newNodeId,
          onDataChange: (newData) => handleNodeDataChange(newNodeId, newData),
        },
      };
      setNodes((nds) => nds.concat(newNode));
    },
    [reactFlowInstance, setNodes, handleNodeDataChange]
  );

  const handleSave = () => {
    const scenarioPayload = {
      name: name || 'Без названия',
      schedule: schedule,
      is_active: isActive,
      nodes: nodes.map((n) => ({
        ...n,
        data: { ...n.data, onDataChange: undefined },
      })),
      edges,
    };
    mutation.mutate(scenarioPayload);
  };

  if (isLoadingScenario)
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100%',
        }}
      >
        <CircularProgress />
      </Box>
    );

  return (
    <Box
      sx={{
        height: 'calc(100vh - 64px)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Paper
        sx={{
          p: 2,
          display: 'flex',
          gap: 2,
          flexWrap: 'wrap',
          alignItems: 'center',
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <TextField
          label="Название сценария"
          value={name}
          onChange={(e) => setName(e.target.value)}
          size="small"
        />
        <CronBuilder schedule={schedule} setSchedule={setSchedule} />
        <FormControlLabel
          control={
            <Switch
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
          }
          label="Активен"
        />
        <Box sx={{ flexGrow: 1 }} />
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={mutation.isLoading}
        >
          {mutation.isLoading ? <CircularProgress size={24} /> : 'Сохранить'}
        </Button>
      </Paper>
      <Box sx={{ flexGrow: 1, display: 'flex' }}>
        <ReactFlowProvider>
          <Sidebar />
          <Box sx={{ flexGrow: 1, height: '100%' }} ref={reactFlowWrapper}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onInit={setReactFlowInstance}
              nodeTypes={nodeTypes}
              fitView
            >
              <Background />
              <Controls />
            </ReactFlow>
          </Box>
        </ReactFlowProvider>
      </Box>
    </Box>
  );
};

export default ScenarioEditorPage;
