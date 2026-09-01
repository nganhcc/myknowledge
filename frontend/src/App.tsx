import { Routes, Route } from "react-router-dom";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Placeholder />} />
    </Routes>
  );
}

function Placeholder() {
  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <h1>AI Knowledge Base</h1>
      <p>Frontend scaffold ready. Pages land in upcoming phases.</p>
    </main>
  );
}

export default App;