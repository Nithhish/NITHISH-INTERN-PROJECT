import os
import base64
from openai import OpenAI

def get_gpt_response(user_message: str, context: dict = None):
    """
    Get a response from ChatGPT with player context and session stats.
    Supports gpt-4o vision for image analysis.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "OpenAI API Key not configured."
        
    client = OpenAI(api_key=api_key)
    
    # Base instructions
    system_prompt = "You are ChatGPT, now integrated as an elite Cricket Performance Coach. "
    system_prompt += "Perform an 'Examination' (XAM) of the player's posture and technique if an image is provided. "
    system_prompt += "Reference the visual details from the image if provided. "
    system_prompt += "Provide drills and progress tracking based on biomechanical data."
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Context aggregation
    content = [user_message]
    
    if context:
        player = context.get('player')
        if player:
            content.append(f"\nPLAYER: {player.get('name')} ({player.get('email')})")
            
        career = context.get('career_stats')
        if career:
            content.append(
                f"\nCAREER STATS:\n- Sessions: {career['total_sessions']}\n"
                f"- Avg Score: {career['avg_career_score']:.1f}\n"
                f"- Max Speed: {career['max_swing_speed']:.1f}"
            )
            
        current = context.get('current_session')
        if current:
            shots = current.get('shots', [])
            avg_tech = sum(s.get('technique_score', 0) for s in shots) / len(shots) if shots else 0
            content.append(
                f"\nCURRENT SESSION ({current.get('media_type')}):\n"
                f"- File: {current.get('filename')}\n"
                f"- Current Avg Score: {avg_tech:.1f}/100"
            )
            
            # If image, add to vision
            if current.get('media_type') == 'image' and current.get('file_path'):
                try:
                    f_path = current.get('file_path')
                    if os.path.exists(f_path):
                        with open(f_path, "rb") as image_file:
                            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                        
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Analyzing this posture image:"},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{encoded_string}"}
                                }
                            ]
                        })
                except Exception as e:
                    print(f"[ERR] Vision encoding failed: {e}")

    messages.append({"role": "user", "content": "\n".join(content)})
            
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error contacting GPT-4o: {str(e)}"
