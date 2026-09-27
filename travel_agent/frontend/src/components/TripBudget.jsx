export default function TripBudget({ trip }) {
  const budget = trip.budget || {};
  const currency = budget.currency || 'USD';

  const flightCost = budget.flight_actual || 0;
  const hotelCost = budget.hotel_actual || 0;
  const activitiesCost = budget.activities_estimated || 0;
  const totalEstimated = flightCost + hotelCost + activitiesCost;
  const maxBudget = budget.max_total || 0;
  const remaining = maxBudget > 0 ? maxBudget - totalEstimated : null;

  const formatCurrency = (amount) => {
    return `${currency} ${amount.toLocaleString()}`;
  };

  if (totalEstimated === 0 && maxBudget === 0) {
    return null;
  }

  return (
    <div className="trip-budget">
      <h3>💰 Budget</h3>
      <div className="budget-breakdown">
        {flightCost > 0 && (
          <div className="budget-row">
            <span className="budget-label">Flights</span>
            <span className="budget-value">{formatCurrency(flightCost)}</span>
          </div>
        )}
        {hotelCost > 0 && (
          <div className="budget-row">
            <span className="budget-label">Hotel</span>
            <span className="budget-value">{formatCurrency(hotelCost)}</span>
          </div>
        )}
        {activitiesCost > 0 && (
          <div className="budget-row">
            <span className="budget-label">Activities (estimated)</span>
            <span className="budget-value">~{formatCurrency(activitiesCost)}</span>
          </div>
        )}
        <div className="budget-row budget-total">
          <span className="budget-label">Total</span>
          <span className="budget-value">~{formatCurrency(totalEstimated)}</span>
        </div>
        {maxBudget > 0 && (
          <>
            <div className="budget-row">
              <span className="budget-label">Budget</span>
              <span className="budget-value">{formatCurrency(maxBudget)}</span>
            </div>
            <div className={`budget-row budget-remaining ${remaining < 0 ? 'over-budget' : ''}`}>
              <span className="budget-label">Remaining</span>
              <span className="budget-value">
                {remaining >= 0 ? formatCurrency(remaining) : `Over by ${formatCurrency(Math.abs(remaining))}`}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
