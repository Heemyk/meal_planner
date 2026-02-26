import { useState } from "react";
import { createPlan, uploadRecipes } from "./api.js";
import { logger } from "./logger.js";

export default function App() {
  const [files, setFiles] = useState([]);
  const [uploadResult, setUploadResult] = useState(null);
  const [targetServings, setTargetServings] = useState(10);
  const [planResult, setPlanResult] = useState(null);
  const [error, setError] = useState(null);
  const uiLogger = logger.child("ui");

  const handleUpload = async () => {
    setError(null);
    try {
      uiLogger.info("upload.click");
      const result = await uploadRecipes(files);
      setUploadResult(result);
    } catch (err) {
      uiLogger.error("upload.failed", err);
      setError(err.message);
    }
  };

  const handlePlan = async () => {
    setError(null);
    try {
      uiLogger.info("plan.click", { targetServings });
      const result = await createPlan(Number(targetServings));
      setPlanResult(result);
    } catch (err) {
      uiLogger.error("plan.failed", err);
      setError(err.message);
    }
  };

  return (
    <div className="container">
      <header>
        <h1>Tandem Recipe Planner</h1>
        <p>Upload recipe text files, then generate a meal plan.</p>
      </header>

      <section className="card">
        <h2>Upload Recipes</h2>
        <input
          type="file"
          multiple
          onChange={(event) => {
            setFiles(event.target.files);
            uiLogger.info("files.selected", { count: event.target.files.length });
          }}
        />
        <button onClick={handleUpload} disabled={!files.length}>
          Upload
        </button>
        {uploadResult && (
          <pre className="output">{JSON.stringify(uploadResult, null, 2)}</pre>
        )}
      </section>

      <section className="card">
        <h2>Create Plan</h2>
        <label>
          Target servings
          <input
            type="number"
            min="1"
            value={targetServings}
            onChange={(event) => setTargetServings(event.target.value)}
          />
        </label>
        <button onClick={handlePlan}>Generate Plan</button>
        {planResult && (
          <pre className="output">{JSON.stringify(planResult, null, 2)}</pre>
        )}
      </section>

      {error && <div className="error">{error}</div>}
    </div>
  );
}
