/**
 * Compute SHAP-like feature contribution values for model interpretability.
 *
 * SHAP value for feature i, sample j = x_value[i][j] * coefficient[i]
 * This gives per-sample, per-feature contribution to the prediction score.
 */
export function useShapValues() {
  /**
   * Compute the SHAP matrix from barcode data and model coefficients.
   *
   * @param {Object} barcodeData - from /api/data-explore/{pid}/barcode-data
   *   { matrix: number[][], feature_names: string[], sample_names: string[], sample_classes: number[] }
   * @param {Object} bestIndividual - from results.best_individual
   *   { features: { indexStr: coefficient }, ... }
   * @param {string[]} allFeatureNames - from results.feature_names (maps indices to names)
   * @returns {Object} { shapMatrix, featureNames, sampleNames, sampleClasses, featureValues, featureImportance }
   */
  function computeShapMatrix(barcodeData, bestIndividual, allFeatureNames) {
    const { matrix, feature_names: barcodeFeatures, sample_names: sampleNames, sample_classes: sampleClasses } = barcodeData

    // Build coefficient map: feature_name -> coefficient
    const coeffMap = {}
    for (const [idxStr, coef] of Object.entries(bestIndividual.features || {})) {
      const idx = parseInt(idxStr)
      const name = allFeatureNames[idx] || `feature_${idx}`
      coeffMap[name] = parseFloat(coef)
    }

    // matrix[i][j] = value of feature i for sample j (features in rows)
    // shapMatrix[i][j] = matrix[i][j] * coefficient[i]
    const featureNames = []
    const shapMatrix = []
    const featureValues = []
    const coefficients = []

    for (let fi = 0; fi < barcodeFeatures.length; fi++) {
      const fname = barcodeFeatures[fi]
      const coef = coeffMap[fname]
      if (coef === undefined) continue

      featureNames.push(fname)
      coefficients.push(coef)
      featureValues.push(matrix[fi] || [])
      shapMatrix.push((matrix[fi] || []).map(val => val * coef))
    }

    // Compute feature importance = mean |SHAP| per feature
    const featureImportance = featureNames.map((name, fi) => {
      const row = shapMatrix[fi]
      const meanAbsShap = row.reduce((sum, v) => sum + Math.abs(v), 0) / (row.length || 1)
      return { name, index: fi, meanAbsShap, coefficient: coefficients[fi] }
    })
    featureImportance.sort((a, b) => b.meanAbsShap - a.meanAbsShap)

    return {
      shapMatrix,
      featureNames,
      sampleNames: sampleNames || [],
      sampleClasses: sampleClasses || [],
      featureValues,
      featureImportance,
      coefficients,
    }
  }

  return { computeShapMatrix }
}
