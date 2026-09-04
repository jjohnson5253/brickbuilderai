import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ClaimGenerationApiService } from '../src/services/claimGenerationApi';
import { CreateCheckoutSessionApiService } from '../src/services/createCheckoutSessionApi';
import { EstimatePriceApiService } from '../src/services/estimatePriceApi';
import { GetCommunityGenerationsApiService } from '../src/services/getCommunityGenerationsApi';
import { GetGenerationsByImageApiService } from '../src/services/getGenerationsByImageApi';
import { GetPriceApiService } from '../src/services/getPriceApi';
import { GetUserGenerationsApiService } from '../src/services/getUserGenerationsApi';
import { LdrToMpdApiService } from '../src/services/ldrToMpdApi';
import { LlmRenderApiService } from '../src/services/llmRenderApi';
import { PromptEditModelApiService } from '../src/services/promptEditModelApi';
import { ResizeModelApiService } from '../src/services/resizeModelApi';
import { SendWaitlistEmailApiService } from '../src/services/sendWaitlistEmailApi';
import { ToggleIsCommunityApiService } from '../src/services/toggleIsCommunityApi';
import { UpdateGenerationNameApiService } from '../src/services/updateGenerationNameApi';
import { UpdateImagePreviewApiService } from '../src/services/updateImagePreviewApi';
import { UpdateModelApiService } from '../src/services/updateModelApi';
import { UpdateUsernameApiService, UsernameTakenError } from '../src/services/updateUsernameApi';

const ok = (data: unknown) => ({ ok: true, status: 200, statusText: 'OK', json: vi.fn().mockResolvedValue(data), text: vi.fn() });
const fail = (status = 400, text = 'bad request') => ({ ok: false, status, statusText: 'Bad Request', json: vi.fn(), text: vi.fn().mockResolvedValue(text) });

describe('JSON API service contracts', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn()));

  const cases: Array<[string, () => Promise<unknown>, string, unknown, unknown]> = [
    ['claim', () => ClaimGenerationApiService.claimGeneration('g1', 'tok'), '/claimGeneration', { generation_id: 'g1' }, { generation_id: 'g1', claimed: true }],
    ['checkout', () => CreateCheckoutSessionApiService.createCheckoutSession({ quantity: 2 }, 'tok'), '/createCheckoutSession', { quantity: 2 }, { session_id: 's1', checkout_url: 'url' }],
    ['community', () => GetCommunityGenerationsApiService.getCommunityGenerations('tok', 10, 2, true), '/getCommunityGenerations', { limit: 10, offset: 2, processing: true }, { generations: [], total_count: 0, has_more: false }],
    ['by image', () => GetGenerationsByImageApiService.getGenerationsByImage('tok', 'img'), '/getGenerationsByImage', { processed_image_url: 'img' }, { generations: [], total_count: 0 }],
    ['user generations', () => GetUserGenerationsApiService.getUserGenerations('tok', 10, 3, false), '/getUserGenerations', { limit: 10, offset: 3, processing: false }, { generations: [], total_count: 0, has_more: false }],
    ['prompt edit', () => PromptEditModelApiService.promptEditModel('g1', 'blue', 'tok', 'a'), '/promptEditModel', { generation_id: 'g1', edit_prompt: 'blue', model_option: 'a' }, { generation_id: 'g2', message: 'ok' }],
    ['resize', () => ResizeModelApiService.resizeModel('g1', 24, 'tok'), '/resizeModel', { generation_id: 'g1', detail_level: 24, use_red_bricks: true }, { generation_id: 'g2', message: 'ok' }],
    ['toggle', () => ToggleIsCommunityApiService.toggleIsCommunity('g1', 'tok'), '/toggleIsCommunity', { generation_id: 'g1' }, { generation_id: 'g1', is_community: true }],
    ['rename', () => UpdateGenerationNameApiService.updateGenerationName('g1', 'Castle', 'tok'), '/updateGenerationName', { generation_id: 'g1', name: 'Castle' }, { generation_id: 'g1', name: 'Castle' }],
    ['preview', () => UpdateImagePreviewApiService.updateImagePreview('g1', 'base64', 'tok'), '/updateImagePreview', { generation_id: 'g1', image_base64: 'base64' }, { generation_id: 'g1', preview_image_url: 'url' }],
    ['model', () => UpdateModelApiService.updateModel('g1', '0 0 0', 'tok'), '/updateModel', { generation_id: 'g1', xyzrgb_content: '0 0 0' }, { generation_id: 'g1', success: true }],
    ['username', () => UpdateUsernameApiService.updateUsername('builder', 'tok'), '/updateUsername', { username: 'builder' }, { username: 'builder' }],
    ['ldr', () => LdrToMpdApiService.convertLdrToMpd('ldr', 'castle', 'tok'), '/ldrToMpd', { ldr_content: 'ldr', model_name: 'castle' }, { mpd_content: 'mpd', message: 'ok' }],
    ['llm render', () => LlmRenderApiService.llmRender('xyz', ['image', 'image2'], 'paint', 'tok'), '/llmRender', { xyzrgb_url: 'xyz', reference_image_urls: ['image', 'image2'], prompt: 'paint' }, { xyzrgb_content: 'xyz', voxel_count: 1, segment_count: 1, model: 'm', applied_rules: [], message: 'ok' }],
  ];

  it.each(cases)('%s sends the documented request and returns JSON', async (_name, invoke, endpoint, body, result) => {
    vi.mocked(fetch).mockResolvedValueOnce(ok(result) as unknown as Response);
    await expect(invoke()).resolves.toEqual(result);
    const [url, options] = vi.mocked(fetch).mock.calls[0];
    expect(String(url).endsWith(endpoint)).toBe(true);
    expect(options).toMatchObject({ method: 'POST', body: JSON.stringify(body) });
    expect((options?.headers as Record<string, string>).Authorization).toBe('Bearer tok');
  });

  it('persists pricing results used by checkout', async () => {
    const estimate = { cart_id: 'cart', parts_list: [{ design_id: '1', color_id: '2', quantity: 3 }], unmapped_parts: 0 };
    vi.mocked(fetch).mockResolvedValueOnce(ok(estimate) as unknown as Response);
    await EstimatePriceApiService.estimatePrice('ldr');
    expect(localStorage.getItem('current_cart_id')).toBe('cart');
    expect(JSON.parse(localStorage.getItem('current_parts_list')!)).toEqual(estimate.parts_list);

    const price = { generation_id: 'g', parts_breakdown: [{ part_id: '3001.dat' }] };
    vi.mocked(fetch).mockResolvedValueOnce(ok(price) as unknown as Response);
    await GetPriceApiService.getPrice('g');
    expect(JSON.parse(localStorage.getItem('current_parts_list')!)).toEqual(price.parts_breakdown);
  });

  it('normalizes waitlist emails and returns server failures as data', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(ok({ success: true }) as unknown as Response);
    await SendWaitlistEmailApiService.sendWaitlistEmail(' Test@Example.COM ');
    expect(JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string)).toEqual({ email: 'test@example.com' });
    vi.mocked(fetch).mockResolvedValueOnce(fail(422, '{"message":"invalid"}') as unknown as Response);
    await expect(SendWaitlistEmailApiService.sendWaitlistEmail('x@y.com')).resolves.toEqual({ success: false, error: 'invalid' });
  });

  it('surfaces API failures and the username conflict type', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(fail(500, 'broken') as unknown as Response);
    await expect(UpdateModelApiService.updateModel('g', 'xyz')).rejects.toThrow('API error: 500 - broken');
    vi.mocked(fetch).mockResolvedValueOnce(fail(409, 'taken') as unknown as Response);
    await expect(UpdateUsernameApiService.updateUsername('taken')).rejects.toBeInstanceOf(UsernameTakenError);
  });

  it('validates required values before making requests', async () => {
    await expect(EstimatePriceApiService.estimatePrice('')).rejects.toThrow('LDR content is required');
    await expect(GetPriceApiService.getPrice('')).rejects.toThrow('Generation ID is required');
    await expect(LdrToMpdApiService.convertLdrToMpd('')).rejects.toThrow('LDR content is required');
    await expect(SendWaitlistEmailApiService.sendWaitlistEmail('')).rejects.toThrow('Email is required');
    expect(fetch).not.toHaveBeenCalled();
  });
});
