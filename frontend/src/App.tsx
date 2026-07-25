import { Routes, Route } from 'react-router-dom';
import { CommandDeck } from './components/layout/CommandDeck';
import { JobDetail } from './components/detail/JobDetail';
import { AbTestingPage } from './components/abtest/AbTestingPage';

function JobDetailRoute() {
  return <JobDetail />;
}

export default function App() {
  return (
    <Routes>
      <Route element={<CommandDeck />}>
        <Route index element={null} />
        <Route path="ab-testing" element={<AbTestingPage />} />
        <Route path="jobs/:jobId" element={<JobDetailRoute />} />
      </Route>
    </Routes>
  );
}
