import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

import './index.css';
import App from './App.tsx';
import Dashboard from './pages/Dashboard.tsx';
import ConversationList from './pages/ConversationList.tsx';
import ConversationDetail from './pages/ConversationDetail.tsx';
import ProjectList from './pages/ProjectList.tsx';
import ProjectDetail from './pages/ProjectDetail.tsx';
import Upload from './pages/Upload.tsx';
import Ingestion from './pages/Ingestion.tsx';
import Setup from './pages/Setup.tsx';
import { queryClient } from './lib/queryClient';
import { WorkspaceProvider } from './contexts/WorkspaceContext';

const router = createBrowserRouter([
  {
    path: '/setup',
    element: <Setup />,
  },
  {
    path: '/',
    element: <App />,
    children: [
      {
        index: true,
        element: <Dashboard />,
      },
      {
        path: 'conversations',
        element: <ConversationList />,
      },
      {
        path: 'conversations/:id',
        element: <ConversationDetail />,
      },
      {
        path: 'projects',
        element: <ProjectList />,
      },
      {
        path: 'projects/:id',
        element: <ProjectDetail />,
      },
      {
        path: 'upload',
        element: <Upload />,
      },
      {
        path: 'ingestion',
        element: <Ingestion />,
      },
    ],
  },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <WorkspaceProvider>
        <RouterProvider router={router} />
        <ReactQueryDevtools initialIsOpen={false} />
      </WorkspaceProvider>
    </QueryClientProvider>
  </StrictMode>
);
