export const FEEDBACK_ENDPOINT = 'https://formspree.io/f/meaorrye';
export const MAX_FEEDBACK_LENGTH = 5000;

export async function sendFeedback(description: string, email: string | undefined, page: string): Promise<void> {
  const message = description.trim();
  if (!message) throw new Error('Please enter a description.');
  if (message.length > MAX_FEEDBACK_LENGTH) throw new Error('Please keep feedback under 5,000 characters.');

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20_000);
  try {
    const response = await fetch(FEEDBACK_ENDPOINT, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({
        description: message,
        user: email || 'anon user',
        ...(email ? { email } : {}),
        page,
      }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error('Feedback could not be sent. Please try again.');
  } catch {
    throw new Error('Feedback could not be sent. Please try again.');
  } finally {
    clearTimeout(timeout);
  }
}
